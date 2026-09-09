import { NextResponse } from "next/server";
const fallback = "https://github.com/dfhh40245-gif/clpz/releases/latest/download/CLPZ-Setup-Windows-x64.exe";
export function GET() { return NextResponse.redirect(new URL(process.env.DOWNLOAD_URL || fallback), 307); }
