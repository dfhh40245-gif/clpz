import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { SmokeyBackground } from "@/components/smokey-background";
import { AuthForm } from "./auth-form";

export default async function LoginPage() {
  let signedIn = false;
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    signedIn = !!data.user;
  } catch { /* The form explains missing configuration if clicked. */ }
  if (signedIn) redirect("/account");

  return <main className="auth-page"><SmokeyBackground /><nav className="nav shell auth-nav"><Brand /><ThemeToggle /></nav><AuthForm /></main>;
}
