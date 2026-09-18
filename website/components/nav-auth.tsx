"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createBrowserClient } from "@supabase/ssr";

type SessionState =
  | { status: "unknown" }
  | { status: "signed-out" }
  | { status: "signed-in"; email: string; avatarUrl: string | null };

function readAvatarUrl(metadata: Record<string, unknown> | undefined): string | null {
  const url = metadata?.avatar_url;
  return typeof url === "string" && url.startsWith("http") ? url : null;
}

/**
 * Session-aware navigation auth slot (client-side).
 *
 * Signed out (or while unknown): nothing for signed-in users to see wrong —
 * unknown renders nothing, signed-out renders the Sign in link.
 * Signed in: circular profile avatar (Google photo when available, otherwise
 * the default person glyph) linking to /account.
 */
export function NavAuth({ variant = "desktop" }: { variant?: "desktop" | "mobile" }) {
  const [state, setState] = useState<SessionState>({ status: "unknown" });

  useEffect(() => {
    let active = true;
    let subscription: { unsubscribe: () => void } | null = null;
    try {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
      if (!url || !key) throw new Error("Supabase public environment is not configured");
      const supabase = createBrowserClient(url, key);

      const read = async () => {
        try {
          const { data: { user } } = await supabase.auth.getUser();
          if (!active) return;
          setState(user
            ? { status: "signed-in", email: user.email ?? "", avatarUrl: readAvatarUrl(user.user_metadata) }
            : { status: "signed-out" });
        } catch {
          if (active) setState({ status: "signed-out" });
        }
      };
      void read();

      const { data } = supabase.auth.onAuthStateChange((event) => {
        if (event === "SIGNED_IN" || event === "SIGNED_OUT" || event === "USER_UPDATED") void read();
      });
      subscription = data.subscription;
    } catch {
      if (active) setState({ status: "signed-out" });
    }
    return () => { active = false; subscription?.unsubscribe(); };
  }, []);

  if (state.status === "unknown") return null;
  if (state.status === "signed-out") {
    return variant === "mobile"
      ? <Link href="/login" onClick={undefined}>Sign in</Link>
      : <Link href="/login" className="desktop-signin">Sign in</Link>;
  }
  const label = state.email ? `Your account (${state.email})` : "Your account";
  return (
    <Link href="/account" className="nav-avatar" aria-label={label} title={label}>
      {state.avatarUrl
        ? <img src={state.avatarUrl} alt="" width={34} height={34} referrerPolicy="no-referrer" />
        : <DefaultAvatar />}
    </Link>
  );
}

/** Default person glyph matching the site's monochrome avatar style. */
function DefaultAvatar() {
  return (
    <svg viewBox="0 0 36 36" width="34" height="34" aria-hidden="true" focusable="false">
      <defs>
        <clipPath id="clpz-nav-avatar-clip"><circle cx="18" cy="18" r="16" /></clipPath>
      </defs>
      <circle cx="18" cy="18" r="16.5" fill="#e6e4e1" stroke="#1d1914" strokeWidth="2" />
      <g clipPath="url(#clpz-nav-avatar-clip)" fill="#f7f5f2" stroke="#1d1914" strokeWidth="2">
        <circle cx="18" cy="13.5" r="6" />
        <path d="M5.5 35a12.5 12.5 0 0 1 25 0Z" />
      </g>
    </svg>
  );
}
