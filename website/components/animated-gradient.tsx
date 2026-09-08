"use client";

import { useEffect, useRef } from "react";

export function AnimatedGradient({ className = "" }: { className?: string }) {
  const lightRef = useRef<HTMLDivElement>(null);
  const darkRef = useRef<HTMLDivElement>(null);
  const pointerRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    let frame = 0;
    const start = performance.now();
    const trackPointer = (event: PointerEvent) => { pointerRef.current = { x: (event.clientX / innerWidth - .5) * 12, y: (event.clientY / innerHeight - .5) * 12 }; };
    window.addEventListener("pointermove", trackPointer, { passive: true });
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const paint = (now: number) => {
      const t = (now - start) / 1000;
      const pointer = pointerRef.current;
      if (lightRef.current) {
        const ph=t*.86, amt=.72, p1=0, p2=2.1, p3=4.2;
        const dx1=(Math.sin(ph*.55+p1)-Math.sin(p1))*14*amt, dy1=(Math.sin(ph*.43+p1*1.3)-Math.sin(p1*1.3))*14*amt;
        const dx2=(Math.sin(ph*.55+p2)-Math.sin(p2))*14*amt, dy2=(Math.sin(ph*.43+p2*1.3)-Math.sin(p2*1.3))*14*amt;
        const dx3=(Math.sin(ph*.55+p3)-Math.sin(p3))*14*amt, dy3=(Math.sin(ph*.43+p3*1.3)-Math.sin(p3*1.3))*14*amt;
        lightRef.current.style.background = `radial-gradient(circle at ${68.1+dx1+pointer.x}% ${46.03+dy1+pointer.y}%,rgba(240,160,48,1) 0%,rgba(240,160,48,.844) 10.28%,rgba(240,160,48,.5) 20.55%,rgba(240,160,48,.156) 30.83%,rgba(240,160,48,0) 41.1%),radial-gradient(circle at ${25.17+dx2-pointer.x*.6}% ${75.99+dy2-pointer.y*.6}%,rgba(212,138,32,1) 0%,rgba(212,138,32,.844) 11.15%,rgba(212,138,32,.5) 22.3%,rgba(212,138,32,.156) 33.45%,rgba(212,138,32,0) 44.6%),radial-gradient(circle at ${53.11+dx3+pointer.x*.35}% ${12.71+dy3+pointer.y*.35}%,rgba(250,249,239,1) 0%,rgba(250,249,239,.844) 16.66%,rgba(250,249,239,.5) 33.33%,rgba(250,249,239,.156) 49.99%,rgba(250,249,239,0) 66.65%),#faf9ef`;
      }
      if (darkRef.current) {
        const ph=t, ps=[0,1.7,3.4,5.1];
        const d=ps.map(p=>[(Math.sin(ph*.55+p)-Math.sin(p))*14,(Math.sin(ph*.43+p*1.3)-Math.sin(p*1.3))*14]);
        darkRef.current.style.background = `radial-gradient(circle at ${67.04+d[0][0]+pointer.x}% ${45.93+d[0][1]+pointer.y}%,rgba(8,8,8,1) 0%,rgba(8,8,8,.844) 19.02%,rgba(8,8,8,.5) 38.05%,rgba(8,8,8,.156) 57.07%,rgba(8,8,8,0) 76.1%),radial-gradient(circle at ${35.47+d[1][0]-pointer.x*.55}% ${65.92+d[1][1]-pointer.y*.55}%,rgba(60,42,18,1) 0%,rgba(60,42,18,.844) 12.9%,rgba(60,42,18,.5) 25.8%,rgba(60,42,18,.156) 38.7%,rgba(60,42,18,0) 51.6%),radial-gradient(circle at ${48.33+d[2][0]+pointer.x*.4}% ${20.11+d[2][1]+pointer.y*.4}%,rgba(240,160,48,1) 0%,rgba(240,160,48,.844) 16.75%,rgba(240,160,48,.5) 33.5%,rgba(240,160,48,.156) 50.25%,rgba(240,160,48,0) 67%),radial-gradient(circle at ${80.81+d[3][0]-pointer.x*.25}% ${88.03+d[3][1]-pointer.y*.25}%,rgba(245,239,229,1) 0%,rgba(245,239,229,.844) 10.28%,rgba(245,239,229,.5) 20.55%,rgba(245,239,229,.156) 30.83%,rgba(245,239,229,0) 41.1%),#050505`;
      }
      if (!reduced) frame = requestAnimationFrame(paint);
    };
    frame = requestAnimationFrame(paint);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("pointermove", trackPointer); };
  }, []);

  return <div className={`animated-gradient ${className}`} aria-hidden="true"><div ref={lightRef} className="gradient-layer gradient-light"/><div ref={darkRef} className="gradient-layer gradient-dark"/></div>;
}
