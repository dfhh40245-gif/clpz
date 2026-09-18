import { NextResponse } from "next/server";

// Product → checkout URL mapping (server-owned).
const products: Record<string, string | undefined> = {
  creator: process.env.GUMROAD_CREATOR_URL || process.env.GUMROAD_PRODUCT_URL,
  "credits-50": process.env.GUMROAD_CREDITS_50_URL,
  "credits-200": process.env.GUMROAD_CREDITS_200_URL,
};

// ── Fail-closed launch gate (task 15 / F19) ────────────────────────────
// Configured URLs are NOT sufficient to open checkout. Payments go live only
// when the owner explicitly sets CHECKOUT_ENABLED=1 after the payment
// lifecycle acceptance checks pass (ACCEPTANCE.md gate 15). Default: closed —
// the /buy page's "coming soon" statement stays truthful regardless of what
// URLs happen to be configured in the environment.
const CHECKOUT_OPEN = process.env.CHECKOUT_ENABLED === "1";

export function GET(request: Request) {
  const plan = new URL(request.url).searchParams.get("plan") || "creator";
  const url = products[plan];
  if (!CHECKOUT_OPEN || !url) {
    return NextResponse.json(
      { error: "Checkout is not open." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  return NextResponse.json({ url }, { headers: { "Cache-Control": "public, max-age=300" } });
}
