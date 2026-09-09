import { NextRequest, NextResponse } from "next/server";

export function GET(request: NextRequest) {
  const destination = process.env.ANDROID_DOWNLOAD_URL || "/downloads/CLPZ-Mobile.apk";
  return NextResponse.redirect(new URL(destination, request.url), 307);
}
