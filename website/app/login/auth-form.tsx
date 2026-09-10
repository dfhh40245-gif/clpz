"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Brand } from "@/components/brand";
import { GoogleButton } from "./google-button";

type Mode = "login" | "signup";

export function AuthForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function switchMode(next: Mode) {
    setMode(next); setMessage(""); setSuccess(false); setPassword(""); setConfirm(""); setShowPassword(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage(""); setSuccess(false);
    if (mode === "signup" && password !== confirm) { setMessage("Passwords do not match."); return; }
    setBusy(true);
    try {
      const supabase = createClient();
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/account"); router.refresh();
      } else {
        const { data, error } = await supabase.auth.signUp({ email, password, options: { data: { full_name: displayName.trim() || undefined }, emailRedirectTo: `${window.location.origin}/auth/callback?next=/account` } });
        if (error) throw error;
        if (data.session) { router.push("/account"); router.refresh(); }
        else { setSuccess(true); setMessage("Check your email to confirm your account, then sign in."); }
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication could not be completed.");
    } finally { setBusy(false); }
  }

  return <section className="auth-card">
    <Brand />
    <h1>Welcome {mode === "login" ? "Back" : "to CLPZ"}</h1>
    <p>{mode === "login" ? "Sign in to continue" : "Create your account to get started"}</p>
    <div className="auth-tabs" role="group" aria-label="Account action"><button type="button" aria-pressed={mode === "login"} disabled={busy} className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")}>Sign in</button><button type="button" aria-pressed={mode === "signup"} disabled={busy} className={mode === "signup" ? "active" : ""} onClick={() => switchMode("signup")}>Create account</button></div>
    {message && <p className={success ? "auth-message" : "auth-error"} role="status">{message}</p>}
    <form className="auth-form" onSubmit={submit} aria-busy={busy}>
      {mode === "signup" && <label><span>Display name <i>optional</i></span><input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} autoComplete="name" /></label>}
      <label><span>Email address</span><input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" autoCapitalize="none" spellCheck={false} placeholder="you@example.com" required /></label>
      <label htmlFor="password"><span>Password{mode === "signup" && <i>at least 6 characters</i>}</span></label><div className="password-field"><input id="password" type={showPassword ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "signup" ? 6 : undefined} required /><button className="password-reveal" type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Hide" : "Show"}</button></div>
      {mode === "signup" && <label><span>Confirm password</span><input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="new-password" minLength={6} required /></label>}
      <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign In →" : "Create Account →"}</button>
    </form>
    <div className="auth-divider"><span>OR</span></div>
    <GoogleButton />
    <p className="auth-switch">{mode === "login" ? "Don’t have an account?" : "Already have an account?"} <button type="button" disabled={busy} onClick={() => switchMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? "Sign Up" : "Log In"}</button></p>
    <small>By continuing, you agree to the <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</small>
  </section>;
}
