import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { SmokeyBackground } from "@/components/smokey-background";
import { AuthForm } from "./auth-form";

export default async function LoginPage() {
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) redirect("/account");
  } catch { /* The form explains missing configuration if clicked. */ }

  return <main className="auth-page"><SmokeyBackground /><nav className="nav shell auth-nav"><Brand /><ThemeToggle /></nav><AuthForm /></main>;
}
