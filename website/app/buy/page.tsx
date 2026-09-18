import Link from "next/link";
import { SiteNav } from "@/components/site-nav";

const plans = {
  creator: { name: "Creator subscription", price: "$7 / month" },
  "credits-50": { name: "50-credit pack", price: "$4 once" },
  "credits-200": { name: "200-credit pack", price: "$11 once" },
} as const;

export default async function BuyPage({ searchParams }: { searchParams: Promise<{ plan?: string }> }) {
  const requested = (await searchParams).plan || "creator";
  const plan = plans[requested as keyof typeof plans] || plans.creator;
  return <><SiteNav /><main id="main-content" className="checkout-page"><section className="checkout-status"><p className="section-index">COMING SOON</p><h1>{plan.name}</h1><strong>{plan.price}</strong><p>We’re finishing payment setup for this plan. Checkout is not open, and you have not been charged. This page remains authoritative while the checkout gate (CHECKOUT_ENABLED) is closed — configuring payment URLs alone does not open checkout.</p><p>You can start creating now: download the free app, make a draft, and edit or export it on your device.</p><Link className="checkout-button" href="/apps">Get the free app ↗</Link><Link className="checkout-secondary" href="/#get-clpz">Back to plans & credits</Link></section></main></>;
}
