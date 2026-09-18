import type { SupabaseClient } from "@supabase/supabase-js";

/** Read account state from Supabase each time; never infer it from checkout. */
export async function readCloudAccount(db: SupabaseClient, userId: string) {
  const [credits, subscriptions, entitlements] = await Promise.all([
    db.from("credit_accounts").select("balance").eq("user_id", userId).maybeSingle(),
    db.from("subscriptions").select("plan,status,current_period_end,provider")
      .eq("user_id", userId).order("created_at", { ascending: false }).limit(1),
    db.from("entitlements").select("feature,expires_at")
      .eq("user_id", userId).order("created_at", { ascending: false }),
  ]);
  if (credits.error || subscriptions.error || entitlements.error) {
    throw new Error("Cloud account data is unavailable");
  }
  return {
    user_id: userId,
    credits: credits.data?.balance ?? 0,
    subscription: subscriptions.data?.[0] ?? null,
    entitlements: (entitlements.data ?? []).filter(item =>
      !item.expires_at || Date.parse(item.expires_at) > Date.now()),
  };
}
