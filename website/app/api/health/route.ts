import { NextResponse } from "next/server";
export function GET() {
  const configured = { supabase: Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY), gumroad: Boolean(process.env.GUMROAD_PRODUCT_URL && process.env.GUMROAD_PRODUCT_ID), download: Boolean(process.env.DOWNLOAD_URL) };
  return NextResponse.json({ ok: Object.values(configured).every(Boolean), configured }, { headers: { "Cache-Control": "no-store" } });
}
