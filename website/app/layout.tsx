import type { Metadata, Viewport } from "next";
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
export const viewport: Viewport = { themeColor: "#080705", colorScheme: "dark" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
