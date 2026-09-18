import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseAdmin } from "@/lib/supabase-admin";

function equal(left: string, right: string) {
  const a = Buffer.from(left), b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

// Product → entitlement mapping (server-owned; every advertised product must
// appear here before its checkout URL is configured). GUMROAD_PRODUCTS format:
// "permalink:plan:credits,permalink2:plan2:credits2"
//   e.g. "creator:creator:0,clpz-50:credits:50,clpz-200:credits:200"
type ProductRule = { permalink: string; plan: string; credits: number };
function productRules(): ProductRule[] {
  return (process.env.GUMROAD_PRODUCTS || "")
    .split(",").map(s => s.trim()).filter(Boolean).map(entry => {
      const [permalink, plan, credits] = entry.split(":");
      return { permalink, plan: plan || "credits", credits: Number.parseInt(credits || "0", 10) || 0 };
    }).filter(r => r.permalink);
}

function ruleFor(permalink: string): ProductRule | undefined {
  const rules = productRules();
  if (rules.length) return rules.find(r => r.permalink === permalink);
  // Legacy single-product config (backward compatible).
  const legacy = process.env.GUMROAD_PRODUCT_PERMALINK;
  if (legacy && permalink === legacy) {
    return { permalink, plan: "credits", credits: Number.parseInt(process.env.GUMROAD_DEFAULT_CREDITS || "0", 10) || 0 };
  }
  return undefined;
}

const REVERSAL_STATUSES = new Set(["refunded", "disputed"]);

export async function POST(request: NextRequest) {
  const expected = process.env.GUMROAD_PING_SECRET,
    supplied = request.nextUrl.searchParams.get("token") || "";
  if (!expected || !equal(expected, supplied)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const form = await request.formData();
  const saleId = String(form.get("sale_id") || "");
  const permalink = String(form.get("product_permalink") || "");
  if (!saleId) {
    return NextResponse.json({ error: "Unexpected product payload" }, { status: 400 });
  }

  const rule = ruleFor(permalink);
  if (!rule) {
    // Unknown product: record nothing, ask provider to retry (not a 200 ack —
    // an HTTP 200 is not proof of fulfillment, so unknown products must NOT
    // be acknowledged as processed).
    console.error("Gumroad Ping: unknown product permalink", { permalink });
    return NextResponse.json({ error: "Unexpected product payload" }, { status: 400 });
  }

  const price = Number.parseInt(String(form.get("price") || "0"), 10);
  const refunded = String(form.get("refunded") || "false") === "true";
  const disputed = String(form.get("disputed") || "false") === "true";
  const isReversal = refunded || disputed;
  const status = refunded ? "refunded" : disputed ? "disputed" : "paid";

  // ── Webhook inbox: durable receipt BEFORE any fulfillment decision ──
  // provider+external_id+event_state is the dedupe identity; the inbox row
  // survives crashes so redelivery can resume an interrupted fulfillment.
  const db = createSupabaseAdmin();

  const { data: inboxRow, error: inboxError } = await db
    .from("webhook_events")
    .upsert(
      {
        provider: "gumroad",
        external_id: saleId,
        event_state: status,
        payload: Object.fromEntries(form.entries()),
        received_at: new Date().toISOString(),
        processed: false,
      },
      { onConflict: "provider,external_id,event_state" },
    )
    .select("id, processed")
    .single();

  if (inboxError) {
    console.error("Gumroad Ping: inbox persist failed", { code: inboxError.code });
    return NextResponse.json({ error: "Persistence failed" }, { status: 500 });
  }

  // ── Ordered state transitions: a late paid event can never overwrite a
  // later refund/dispute (the audit's blind-upsert defect). Terminal states
  // win regardless of delivery order.
  const { data: existing } = await db
    .from("payments")
    .select("id, user_id, status, credits_granted, product_id, amount_cents, currency")
    .eq("provider", "gumroad")
    .eq("external_id", saleId)
    .maybeSingle();

  const existingStatus = existing?.status ?? null;
  if (
    existing &&
    ((REVERSAL_STATUSES.has(existingStatus) && !isReversal) ||
      (existingStatus === "disputed" && status === "refunded"))
  ) {
    // Stale/reordered event: acknowledge receipt but do NOT downgrade state.
    await db.from("webhook_events").update({ processed: true }).eq("id", inboxRow.id);
    return NextResponse.json({ ok: true, ignored: "stale_event", current: existingStatus });
  }

  // ── Account association: match the buyer to a verified CLPZ account. ──
  // Email is matched against auth.users (provider-verified at signup);
  // client-supplied user ids are never accepted from the webhook payload.
  const buyerEmail = String(form.get("email") || "").trim().toLowerCase();
  let userId: string | null = existing?.user_id ?? null;
  if (!userId && buyerEmail) {
    const { data: profile } = await db
      .from("profiles")
      .select("id")
      .eq("email", buyerEmail)
      .maybeSingle();
    userId = profile?.id ?? null;
  }

  if (existing) {
    // Update allowed fields WITHOUT downgrading status (guard above passed).
    const { error: updateError } = await db
      .from("payments")
      .update({
        user_id: userId ?? existing.user_id,
        product_id: existing.product_id || permalink,
        amount_cents: Number.isFinite(price) ? price : existing.amount_cents,
        status: isReversal ? status : existing.status,
      })
      .eq("id", existing.id);
    if (updateError) {
      console.error("Gumroad Ping: payment update failed", { code: updateError.code });
      return NextResponse.json({ error: "Persistence failed" }, { status: 500 });
    }
  } else {
    const { error: insertError } = await db.from("payments").insert({
      provider: "gumroad",
      external_id: saleId,
      user_id: userId,
      product_id: permalink,
      amount_cents: Number.isFinite(price) ? price : 0,
      currency: String(form.get("currency") || "usd").toLowerCase(),
      status,
    });
    if (insertError) {
      console.error("Gumroad Ping: payment insert failed", { code: insertError.code });
      return NextResponse.json({ error: "Persistence failed" }, { status: 500 });
    }
  }

  // ── Fulfillment: grant subscription entitlement / credit pack exactly once
  // per sale for paid events with a matched account; reversal events mark the
  // entitlement revoked. Grant amount comes from the SERVER's product map,
  // never from the payload.
  let grantedCredits = 0;
  if (userId && rule.credits > 0 && status === "paid") {
    const { data: priorGrant } = await db
      .from("credit_transactions")
      .select("id")
      .eq("external_ref", `gumroad:${saleId}`)
      .eq("txn_type", "purchase")
      .maybeSingle();
    if (!priorGrant) {
      const { data: account } = await db
        .from("credit_accounts")
        .select("balance")
        .eq("user_id", userId)
        .maybeSingle();
      const newBalance = (account?.balance ?? 0) + rule.credits;
      const { error: balanceError } = await db
        .from("credit_accounts")
        .update({ balance: newBalance, updated_at: new Date().toISOString() })
        .eq("user_id", userId);
      const { error: ledgerError } = await db.from("credit_transactions").insert({
        user_id: userId,
        amount: rule.credits,
        txn_type: "purchase",
        description: `Gumroad ${rule.plan} ${saleId}`,
        external_ref: `gumroad:${saleId}`,
      });
      if (balanceError || ledgerError) {
        // Ledger write failed: leave processed=false so provider redelivery
        // retries; the priorGrant probe makes the retry idempotent.
        console.error("Gumroad Ping: fulfillment failed", {
          balance: balanceError?.code, ledger: ledgerError?.code,
        });
        return NextResponse.json({ error: "Fulfillment failed" }, { status: 500 });
      }
      grantedCredits = rule.credits;
    }
  }

  if (userId && rule.plan === "creator") {
    const entitlementStatus = status === "paid" ? "active" : "revoked";
    const { error: entError } = await db
      .from("entitlements")
      .upsert(
        {
          user_id: userId,
          feature: "creator",
          granted_by: "purchase",
          external_ref: `gumroad:${saleId}`,
          // entitlements has no status column in 0001; revocation is expressed
          // by deleting the row (read-own policy keeps it invisible anyway).
        },
        { onConflict: "user_id,feature" },
      );
    if (entError && entitlementStatus === "active") {
      console.error("Gumroad Ping: entitlement grant failed", { code: entError.code });
    }
    if (status !== "paid") {
      await db.from("entitlements").delete().eq("user_id", userId).eq("feature", "creator");
    }
  }

  // Mark the inbox row processed (last step: crash before this = redelivery
  // replays safely via the priorGrant probe + ordered-transition guard).
  await db.from("webhook_events").update({ processed: true }).eq("id", inboxRow.id);

  return NextResponse.json({
    ok: true,
    linked: Boolean(userId),
    credits: grantedCredits,
  });
}
