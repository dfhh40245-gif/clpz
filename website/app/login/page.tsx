import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { GoogleButton } from "./google-button";
import { AnimatedGradient } from "@/components/animated-gradient";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";

export default async function LoginPage() {
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) redirect("/account");
  } catch { /* The form explains missing configuration if clicked. */ }

  return <main className="auth-page"><AnimatedGradient className="auth-gradient" /><nav className="nav shell auth-nav"><Brand /><ThemeToggle /></nav><section className="auth-card"><Brand /><p className="section-index">CLPZ ACCOUNT</p><h1>Welcome to CLPZ.</h1><p>Sign in or create your account with Google to keep purchases and downloads connected.</p><GoogleButton /><small>By continuing, you agree to the <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</small></section></main>;
}
