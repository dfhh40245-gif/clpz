import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { GoogleButton } from "./google-button";

export default async function LoginPage() {
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) redirect("/account");
  } catch { /* The form explains missing configuration if clicked. */ }

  return <main className="auth-page"><nav className="nav shell"><Link className="brand" href="/"><span className="brand-mark"><i>C</i></span><span>CLPZ</span></Link></nav><section className="auth-card"><p className="section-index">CLPZ ACCOUNT</p><h1>Welcome back.</h1><p>Sign in to keep your purchase and downloads connected to one account.</p><GoogleButton /><small>By continuing, you agree to the <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</small></section></main>;
}
