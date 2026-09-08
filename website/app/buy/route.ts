import { NextResponse } from "next/server";
const products: Record<string, string | undefined> = {
  creator: process.env.GUMROAD_CREATOR_URL || process.env.GUMROAD_PRODUCT_URL,
  "credits-50": process.env.GUMROAD_CREDITS_50_URL,
  "credits-200": process.env.GUMROAD_CREDITS_200_URL,
};
export function GET(request: Request) {
  const plan = new URL(request.url).searchParams.get("plan") || "creator";
  const productUrl = products[plan];
  if (!productUrl) return NextResponse.json({ error: "Checkout is being configured. Please try again shortly." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  const checkout = new URL(productUrl);
  checkout.searchParams.set("wanted", "true");
  return NextResponse.redirect(checkout, 307);
}
