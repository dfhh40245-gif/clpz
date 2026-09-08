"use client";

import { useEffect, useRef } from "react";

export function AnimatedGradient({ className = "" }: { className?: string }) {
  const lightRef = useRef<HTMLDivElement>(null);
  const darkRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let frame = 0;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const paint = (time: number) => {
      const t = time * 0.00016;
      if (lightRef.current) {
        const a = 24 + Math.sin(t) * 12, b = 76 + Math.sin(t * .8 + 2) * 12;
        lightRef.current.style.background = `radial-gradient(circle at ${a}% ${32 + Math.sin(t*.7)*14}%,rgba(240,160,48,.38),transparent 44%),radial-gradient(circle at ${b}% ${62 + Math.sin(t*.6+1)*14}%,rgba(212,138,32,.28),transparent 46%),radial-gradient(circle at 50% 15%,rgba(255,252,236,.92),transparent 52%),#faf9ef`;
      }
      if (darkRef.current) {
        const a = 23 + Math.sin(t*.9) * 13, b = 76 + Math.sin(t*.7 + 2) * 14;
        darkRef.current.style.background = `radial-gradient(circle at ${a}% ${30 + Math.sin(t*.65)*15}%,rgba(240,160,48,.24),transparent 40%),radial-gradient(circle at ${b}% ${65 + Math.sin(t*.55+1)*15}%,rgba(60,42,18,.72),transparent 47%),radial-gradient(circle at 52% ${12 + Math.sin(t*.4)*8}%,rgba(245,239,229,.1),transparent 38%),radial-gradient(circle at 14% 80%,rgba(22,27,44,.9),transparent 50%),#161825`;
      }
      if (!reduced) frame = requestAnimationFrame(paint);
    };
    paint(0);
    return () => cancelAnimationFrame(frame);
  }, []);

  return <div className={`animated-gradient ${className}`} aria-hidden="true"><div ref={lightRef} className="gradient-layer gradient-light"/><div ref={darkRef} className="gradient-layer gradient-dark"/></div>;
}
