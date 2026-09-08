import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { AnimatedGradient } from "@/components/animated-gradient";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { AuthForm } from "./auth-form";

export default async function LoginPage() {
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) redirect("/account");
  } catch { /* The form explains missing configuration if clicked. */ }

  return <main className="auth-page"><AnimatedGradient className="auth-gradient" /><nav className="nav shell auth-nav"><Brand /><ThemeToggle /></nav><AuthForm /></main>;
}
