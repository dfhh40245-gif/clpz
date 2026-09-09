"use client";

import { useEffect } from "react";

export function GumroadCheckoutBridge() {
  useEffect(() => {
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href^="/buy?plan="]'));
    links.forEach(async link => {
      try {
        const plan = new URL(link.href).searchParams.get("plan");
        const response = await fetch(`/api/checkout-link?plan=${encodeURIComponent(plan || "creator")}`);
        if (!response.ok) return;
        const data = await response.json() as { url?: string };
        if (!data.url) return;
        const checkout = new URL(data.url);
        checkout.searchParams.set("wanted", "true");
        link.href = checkout.toString();
        link.classList.add("gumroad-button");
        link.dataset.gumroadSingleProduct = "true";
      } catch { /* Keep the safe server fallback when checkout is not configured. */ }
    });
  }, []);
  return null;
}
