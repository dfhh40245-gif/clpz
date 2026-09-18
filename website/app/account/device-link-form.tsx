"use client";

import { FormEvent, useState } from "react";

export function DeviceLinkForm() {
  const [state, setState] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function issue(event: FormEvent) {
    event.preventDefault(); setBusy(true); setCode(""); setMessage("");
    try {
      const response = await fetch("/api/cloud/device-link", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: state.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not create a link code.");
      setCode(data.code);
      setMessage("Enter this code in the desktop app within five minutes. It works once.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create a link code.");
    } finally { setBusy(false); }
  }

  return <section className="account-panel"><div><small>CONNECT WINDOWS</small><h2>Link your cloud account</h2>
    <p>In the Windows app, choose “Connect cloud account” and copy the state shown there. Enter it here to get a one-time code. To remove Windows access later, choose “Disconnect cloud account” in the app; signing out of this website closes only the browser session.</p>
    <form className="auth-form" onSubmit={issue}>
      <label><span>State from Windows app</span><input type="text" value={state} onChange={event => setState(event.target.value)} minLength={32} maxLength={128} required autoComplete="off" /></label>
      <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Creating…" : "Create one-time code"}</button>
    </form>
    {code && <p className="device-link-code"><strong>Code:</strong> <code>{code}</code></p>}
    {message && <p role="status">{message}</p>}
  </div></section>;
}
