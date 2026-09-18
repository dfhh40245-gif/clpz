import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

// F21 fix: the old startsWith("/") + !startsWith("//") guard accepted
// "/\\untrusted.example" — WHATWG URL parsing normalizes the backslash into
// a slash, making the value protocol-relative, so new URL(next, origin)
// resolved OFF-origin after a successful code exchange. Validation now runs
// against the CANONICALIZED URL, not the raw string: the redirect target
// must stay inside the path context (resolve to a same-origin path),
// otherwise the default is used.
function safeNextPath(requested: string | null): string {
  const fallback = "/account";
  if (!requested) return fallback;
  if (!requested.startsWith("/") || requested.startsWith("//")) return fallback;
  // Backslashes are protocol-relative in WHATWG URL parsing: reject outright.
  if (requested.includes("\\")) return fallback;
  // Control characters can smuggle separators in some clients: reject.
  if (/[\t\n\r]/.test(requested)) return fallback;
  // Canonical check: resolve against a placeholder origin; if the result
  // leaves that origin (e.g. "//evil", "https://evil"), reject. This is
  // origin-independent: the actual redirect re-bases the (now provably
  // path-only) value onto the real request origin below.
  try {
    const resolved = new URL(requested, "https://clpz.placeholder");
    if (resolved.origin !== "https://clpz.placeholder") return fallback;
  } catch {
    return fallback;
  }
  return requested;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = safeNextPath(url.searchParams.get("next") || "/account");
  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, url.origin));
  }
  return NextResponse.redirect(new URL("/login?error=oauth", url.origin));
}
