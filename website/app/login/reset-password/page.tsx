"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const supabase = createClient();
      const { data: { user }, error: userError } = await supabase.auth.getUser();
      if (userError || !user) throw new Error("Recovery link expired. Request a new one from sign in.");
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      router.replace("/account"); router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not reset password.");
    } finally { setBusy(false); }
  }
  return <main className="auth-page"><section className="auth-card"><h1>Set a new password</h1>
    <form className="auth-form" onSubmit={submit}><label><span>New password</span><input type="password" minLength={8} autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>
      <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Saving…" : "Save new password"}</button></form>
    {message && <p className="auth-error" role="alert">{message}</p>}
    <p><Link href="/login">Back to sign in</Link></p>
  </section></main>;
}
