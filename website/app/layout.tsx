import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { GumroadCheckoutBridge } from "@/components/gumroad-checkout-bridge";
import "./globals.css";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://clpzit.vercel.app";
export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "CLPZ — Find the clip inside the video", template: "%s | CLPZ" },
  description: "CLPZ turns long videos into focused, captioned vertical clips in a private desktop workflow.",
  applicationName: "CLPZ", alternates: { canonical: "/" },
  openGraph: { title: "CLPZ — Find the clip inside the video", description: "Find the moments worth posting, refine them, and export vertical clips.", url: "/", siteName: "CLPZ", type: "website" },
  robots: { index: true, follow: true }
};
export const viewport: Viewport = { themeColor: [
  { media: "(prefers-color-scheme: light)", color: "#faf9ef" },
  { media: "(prefers-color-scheme: dark)", color: "#161825" }
], colorScheme: "light dark" };
const themeScript = `(function(){try{var t=localStorage.getItem('clpz-theme');var d=t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d)}catch(e){}})()`;
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:themeScript}} /></head><body>{children}<GumroadCheckoutBridge /><Script src="https://gumroad.com/js/gumroad.js" strategy="lazyOnload" /></body></html>; }
