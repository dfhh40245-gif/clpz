import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createSupabaseAdmin } from "@/lib/supabase-admin";
import { DEVICE_LINK_TTL_SECONDS, digest, newSecret, sameOriginPost, validSecret } from "@/lib/cloud-device";

export async function POST(request: Request) {
  if (!sameOriginPost(request)) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ error: "Invalid request" }, { status: 400 }); }
  const state = (body as { state?: unknown })?.state;
  if (!validSecret(state)) return NextResponse.json({ error: "Invalid state" }, { status: 400 });
  try {
    const client = await createClient();
    const { data: { user }, error } = await client.auth.getUser();
    if (error || !user) return NextResponse.json({ error: "Sign in required" }, { status: 401 });
    const code = newSecret();
    const admin = createSupabaseAdmin();
    const { error: insertError } = await admin.from("cloud_device_links").insert({
      code_hash: digest(code), state_hash: digest(state), user_id: user.id,
      expires_at: new Date(Date.now() + DEVICE_LINK_TTL_SECONDS * 1000).toISOString(),
    });
    if (insertError) throw insertError;
    return NextResponse.json({ code, expires_in: DEVICE_LINK_TTL_SECONDS },
      { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Device link unavailable" }, { status: 503 });
  }
}
