import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function AccountPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  const name = user.user_metadata?.full_name || user.user_metadata?.name || "Creator";
  return <main><nav className="nav shell"><Link className="brand" href="/"><span className="brand-mark"><i>C</i></span><span>CLPZ</span></Link><form action="/auth/signout" method="post"><button className="nav-signout" type="submit">Sign out</button></form></nav><section className="account shell"><p className="section-index">YOUR ACCOUNT</p><h1>Hello, {name}.</h1><p className="account-email">{user.email}</p><div className="account-panel"><div><small>DESKTOP APP</small><h2>CLPZ for Windows</h2><p>Download the installer directly, then continue creating on your device.</p></div><a className="button primary" href="/download">Download latest <span>↓</span></a></div><p><a className="text-link" href="/download/android">Download Android APK ↓</a></p><Link className="text-link account-home" href="/">← Back to the storefront</Link></section></main>;
}
