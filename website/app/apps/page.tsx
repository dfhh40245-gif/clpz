import type { Metadata } from "next";
import { SiteNav } from "@/components/site-nav";
import { AppDownloads } from "@/components/app-downloads";
export const metadata: Metadata = { title: "Download the studio", alternates: { canonical: "/apps" } };
export default function AppsPage() {
  return <><SiteNav /><main id="main-content" className="apps-page shell">
    <p className="section-index">MAKE ROOM FOR YOUR NEXT IDEA</p>
    <h1>One idea.<br />Take it anywhere.</h1>
    <p className="page-intro">Pick your studio. The app is free to download, and your original footage stays yours.</p>
    <AppDownloads />
    <section className="install-guide"><div><p className="section-index">FIRST THINGS FIRST</p><h2>From download<br />to your first cut.</h2></div><ol>
      <li><b>Install your studio</b><p>Open the Windows installer or Android APK. On Android, allow installation from your browser if prompted.</p></li>
      <li><b>Bring your footage</b><p>Choose a local video. On mobile, try the editor without an account or sign in with your website account.</p></li>
      <li><b>Make it yours</b><p>Adjust the cut and text, then export. Keep your original video available to reopen saved drafts.</p></li>
    </ol></section>
    <div className="download-note">Already installed an earlier Android preview? If Android reports a signature conflict, save your videos before uninstalling the old preview. Uninstalling removes local drafts.</div>
  </main></>;
}
