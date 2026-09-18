import { NextResponse } from "next/server";
import { createSupabaseAdmin } from "@/lib/supabase-admin";
import { digest, validSecret } from "@/lib/cloud-device";
import { readCloudAccount } from "@/lib/cloud-account";

async function session(request: Request) {
  const bearer = request.headers.get("authorization")?.match(/^Bearer ([A-Za-z0-9_-]+)$/);
  const token = bearer?.[1];
  if (!validSecret(token)) return null;
  const admin = createSupabaseAdmin();
  const { data, error } = await admin.from("cloud_device_sessions")
    .select("user_id,expires_at,revoked_at").eq("token_hash", digest(token)).maybeSingle();
  if (error || !data || data.revoked_at || Date.parse(data.expires_at) <= Date.now()) return null;
  return { admin, userId: data.user_id, tokenHash: digest(token) };
}

export async function GET(request: Request) {
  try {
    const current = await session(request);
    if (!current) return NextResponse.json({ error: "Cloud session expired or revoked" }, { status: 401 });
    const account = await readCloudAccount(current.admin, current.userId);
    return NextResponse.json(account, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Cloud account unavailable" }, { status: 503 });
  }
}

export async function DELETE(request: Request) {
  try {
    const current = await session(request);
    if (!current) return NextResponse.json({ error: "Cloud session expired or revoked" }, { status: 401 });
    const { error } = await current.admin.from("cloud_device_sessions")
      .update({ revoked_at: new Date().toISOString() }).eq("token_hash", current.tokenHash);
    if (error) throw error;
    return NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Could not revoke cloud session" }, { status: 503 });
  }
}
