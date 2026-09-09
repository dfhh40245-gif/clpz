import { NextResponse } from "next/server";

const products: Record<string, string | undefined> = {
  creator: process.env.GUMROAD_CREATOR_URL || process.env.GUMROAD_PRODUCT_URL,
  "credits-50": process.env.GUMROAD_CREDITS_50_URL,
  "credits-200": process.env.GUMROAD_CREDITS_200_URL,
};

export function GET(request: Request) {
  const plan = new URL(request.url).searchParams.get("plan") || "creator";
  const url = products[plan];
  if (!url) return NextResponse.json({ error: "Checkout is not configured." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  return NextResponse.json({ url }, { headers: { "Cache-Control": "public, max-age=300" } });
}
