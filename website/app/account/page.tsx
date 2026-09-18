import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { readCloudAccount } from "@/lib/cloud-account";
import { DeviceLinkForm } from "./device-link-form";

export default async function AccountPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  const name = user.user_metadata?.full_name || user.user_metadata?.name || "Creator";
  let account: Awaited<ReturnType<typeof readCloudAccount>> | null = null;
  try { account = await readCloudAccount(supabase, user.id); } catch { /* Display an unavailable state. */ }
  return <main>
    <nav className="nav shell"><form action="/auth/signout" method="post"><button className="nav-signout" type="submit">Sign out</button></form></nav>
    <section className="account shell">
      <p className="section-index">YOUR ACCOUNT</p><h1>Hello, {name}.</h1><p className="account-email">{user.email}</p>
      <section className="account-panel"><div><small>CLOUD ACCESS</small><h2>Subscription and credits</h2>
        {account ? <><p>Credits: {account.credits}</p><p>Subscription: {account.subscription ? `${account.subscription.plan} (${account.subscription.status})` : "No subscription"}</p>
          <p>Entitlements: {account.entitlements.length ? account.entitlements.map(item => item.feature).join(", ") : "None"}</p></>
          : <p role="status">Cloud account details are unavailable. Please try again later.</p>}
      </div></section>
      <DeviceLinkForm />
      <div className="account-panel"><div><small>DESKTOP APP</small><h2>CLPZ for Windows</h2><p>Download the installer, then continue creating locally.</p></div><a className="button primary" href="/download">Download latest <span>↓</span></a></div>
      <p><a className="text-link" href="/download/android">Download Android preview APK ↓</a></p>
      <Link className="text-link account-home" href="/">← Back to the storefront</Link>
    </section>
  </main>;
}
