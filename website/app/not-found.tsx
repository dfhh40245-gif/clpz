import Link from "next/link";
import { SiteNav } from "@/components/site-nav";
export default function NotFound() { return <><SiteNav /><main id="main-content" className="service-state"><p className="section-index">404 / OUT OF FRAME</p><h1>This page missed the cut.</h1><p>The link may have moved. Your studio is one click away.</p><Link className="button primary" href="/">Back to CLPZ ↗</Link></main></>; }
