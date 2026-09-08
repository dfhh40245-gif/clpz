import { NextResponse } from "next/server";
export function GET() {
  const productUrl = process.env.GUMROAD_PRODUCT_URL;
  if (!productUrl) return NextResponse.json({ error: "Checkout is being configured. Please try again shortly." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  const checkout = new URL(productUrl);
  checkout.searchParams.set("wanted", "true");
  return NextResponse.redirect(checkout, 307);
}
