import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SiteNav } from "@/components/site-nav";
import { AppDownloads } from "@/components/app-downloads";

export default async function AccountPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  const name = user.user_metadata?.full_name || user.user_metadata?.name || "Creator";
  return <><SiteNav /><main id="main-content" className="account shell"><p className="section-index">YOUR ACCOUNT</p><h1>Your next cut starts here.</h1><p className="account-email">Welcome, {name}. Signed in as {user.email}</p><div className="account-plan"><div><p className="section-index">LOCAL STUDIO</p><h2>Create at your own pace.</h2><p>Your editors are ready to download. Optional AI plans are coming soon.</p></div><Link className="button quiet" href="/#get-clpz">Explore plans ↗</Link></div><AppDownloads /><div className="account-plan"><p>Use this same account in the apps. Projects and footage stay on each device.</p><form action="/auth/signout" method="post"><button className="nav-signout" type="submit">Sign out</button></form></div><Link className="text-link account-home" href="/">← Back to the storefront</Link></main></>;
}
