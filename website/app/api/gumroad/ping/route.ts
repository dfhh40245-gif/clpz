import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { createSupabaseAdmin } from "@/lib/supabase-admin";
function equal(left: string, right: string) { const a=Buffer.from(left), b=Buffer.from(right); return a.length===b.length && timingSafeEqual(a,b); }
export async function POST(request: NextRequest) {
  const expected=process.env.GUMROAD_PING_SECRET, supplied=request.nextUrl.searchParams.get("token")||"";
  if (!expected || !equal(expected,supplied)) return NextResponse.json({error:"Unauthorized"},{status:401});
  const form=await request.formData(), saleId=String(form.get("sale_id")||""), permalink=String(form.get("product_permalink")||"");
  if (!saleId || !process.env.GUMROAD_PRODUCT_PERMALINK || permalink!==process.env.GUMROAD_PRODUCT_PERMALINK) return NextResponse.json({error:"Unexpected product payload"},{status:400});
  const price=Number.parseInt(String(form.get("price")||"0"),10), refunded=String(form.get("refunded")||"false")==="true", disputed=String(form.get("disputed")||"false")==="true";
  const {error}=await createSupabaseAdmin().from("payments").upsert({ provider:"gumroad", external_id:saleId, product_id:process.env.GUMROAD_PRODUCT_ID||permalink, amount_cents:Number.isFinite(price)?price:0, currency:String(form.get("currency")||"usd").toLowerCase(), status:refunded?"refunded":disputed?"disputed":"paid" },{onConflict:"provider,external_id"});
  if (error) { console.error("Gumroad Ping persistence failed",{code:error.code}); return NextResponse.json({error:"Persistence failed"},{status:500}); }
  return NextResponse.json({ok:true});
}
