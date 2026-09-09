"use client";

import Link from "next/link";
import { useState } from "react";
import { Brand } from "./brand";
import { ThemeToggle } from "./theme-toggle";

export function SiteNav() {
  const [open, setOpen] = useState(false);
  return <header className="site-header">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <nav className="nav shell" aria-label="Main navigation">
      <Brand />
      <div className="nav-links"><Link href="/#showcase">The studio</Link><Link href="/apps">Get the app</Link><Link href="/#get-clpz">Plans & credits</Link></div>
      <div className="nav-actions"><ThemeToggle /><Link href="/login" className="desktop-signin">Sign in</Link>
        <Link href="/apps" className="nav-cta">Get CLPZ <span aria-hidden="true">↗</span></Link>
        <button className="menu-toggle" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-menu" aria-label={open ? "Close navigation" : "Open navigation"}>{open ? "✕" : "☰"}</button>
      </div>
    </nav>
    {open && <nav id="mobile-menu" className="mobile-menu shell" aria-label="Mobile navigation" onKeyDown={e => { if (e.key === "Escape") setOpen(false); }}>
      {[["The studio", "/#showcase"], ["Get the app", "/apps"], ["Plans & credits", "/#get-clpz"], ["Sign in", "/login"]].map(([label, href]) => <Link key={href} href={href} onClick={() => setOpen(false)}>{label}<span aria-hidden="true">↗</span></Link>)}
    </nav>}
  </header>;
}
