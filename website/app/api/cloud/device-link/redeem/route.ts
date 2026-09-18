import { NextResponse } from "next/server";
import { createSupabaseAdmin } from "@/lib/supabase-admin";
import { DEVICE_TOKEN_TTL_SECONDS, digest, newSecret, validSecret } from "@/lib/cloud-device";

export async function POST(request: Request) {
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ error: "Invalid request" }, { status: 400 }); }
  const { code, state } = (body ?? {}) as { code?: unknown; state?: unknown };
  if (!validSecret(code) || !validSecret(state)) {
    return NextResponse.json({ error: "Invalid link code or state" }, { status: 400 });
  }
  try {
    const token = newSecret();
    const admin = createSupabaseAdmin();
    const { data: userId, error } = await admin.rpc("redeem_cloud_device_link", {
      p_code_hash: digest(code), p_state_hash: digest(state), p_token_hash: digest(token),
    });
    if (error) throw error;
    if (!userId) return NextResponse.json({ error: "Link code invalid or expired" }, { status: 401 });
    return NextResponse.json({
      token, user_id: userId, issuer: new URL(request.url).origin,
      audience: "clpz-desktop", expires_in: DEVICE_TOKEN_TTL_SECONDS,
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Device link unavailable" }, { status: 503 });
  }
}
