import { NextResponse } from "next/server";

const fallback = "https://github.com/dfhh40245-gif/clpz/releases/download/mobile-latest/CLPZ-Mobile.apk";

export function GET() {
  return NextResponse.redirect(new URL(process.env.ANDROID_DOWNLOAD_URL || fallback), 307);
}
