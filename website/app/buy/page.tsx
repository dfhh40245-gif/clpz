import Link from "next/link";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";

const plans = {
  creator: { name: "Creator subscription", price: "$7 / month" },
  "credits-50": { name: "50-credit pack", price: "$4 once" },
  "credits-200": { name: "200-credit pack", price: "$11 once" },
} as const;

export default async function BuyPage({ searchParams }: { searchParams: Promise<{ plan?: string }> }) {
  const requested = (await searchParams).plan || "creator";
  const plan = plans[requested as keyof typeof plans] || plans.creator;
  return <main className="checkout-page"><nav className="nav shell"><Brand /><ThemeToggle /></nav><section className="checkout-status"><p className="section-index">SECURE CHECKOUT</p><h1>{plan.name}</h1><strong>{plan.price}</strong><p>This checkout option is being connected to Gumroad. No payment has been taken.</p><Link className="checkout-button" href="/#get-clpz">Return to plans</Link></section></main>;
}
