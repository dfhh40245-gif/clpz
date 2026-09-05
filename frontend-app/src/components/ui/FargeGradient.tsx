import { useEffect, useRef } from 'react';

/**
 * CLPZ FargeGradient — dark mode animated gradient.
 * Exact Qelvra animation pattern, navy/gold palette.
 */
export default function FargeGradient({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf: number;
    const start = performance.now();

    const p1 = 0, p2 = 1.7, p3 = 3.4, p4 = 5.1;
    const b1x = 67.04, b1y = 45.93;
    const b2x = 35.47, b2y = 65.92;
    const b3x = 48.33, b3y = 20.11;
    const b4x = 80.81, b4y = 88.03;

    const render = (now: number) => {
      const t = (now - start) / 1000;
      const ph = t * 1.00;
      const amt = 1.00;

      const dx1 = (Math.sin(ph * 0.55 + p1) - Math.sin(p1)) * 14 * amt;
      const dy1 = (Math.sin(ph * 0.43 + p1 * 1.3) - Math.sin(p1 * 1.3)) * 14 * amt;
      const dx2 = (Math.sin(ph * 0.55 + p2) - Math.sin(p2)) * 14 * amt;
      const dy2 = (Math.sin(ph * 0.43 + p2 * 1.3) - Math.sin(p2 * 1.3)) * 14 * amt;
      const dx3 = (Math.sin(ph * 0.55 + p3) - Math.sin(p3)) * 14 * amt;
      const dy3 = (Math.sin(ph * 0.43 + p3 * 1.3) - Math.sin(p3 * 1.3)) * 14 * amt;
      const dx4 = (Math.sin(ph * 0.55 + p4) - Math.sin(p4)) * 14 * amt;
      const dy4 = (Math.sin(ph * 0.43 + p4 * 1.3) - Math.sin(p4 * 1.3)) * 14 * amt;

      // CLPZ amber: navy, dark gold, warm amber, cream
      const c1 = '22,27,44';   // deep navy
      const c2 = '60,42,18';   // dark gold
      const c3 = '240,160,48'; // amber
      const c4 = '245,239,229'; // warm cream

      el.style.background = `
        radial-gradient(circle at ${b1x + dx1}% ${b1y + dy1}%, rgba(${c1},1) 0%, rgba(${c1},0.844) 19.02%, rgba(${c1},0.5) 38.05%, rgba(${c1},0.156) 57.07%, rgba(${c1},0) 76.1%),
        radial-gradient(circle at ${b2x + dx2}% ${b2y + dy2}%, rgba(${c2},1) 0%, rgba(${c2},0.844) 12.9%, rgba(${c2},0.5) 25.8%, rgba(${c2},0.156) 38.7%, rgba(${c2},0) 51.6%),
        radial-gradient(circle at ${b3x + dx3}% ${b3y + dy3}%, rgba(${c3},1) 0%, rgba(${c3},0.844) 16.75%, rgba(${c3},0.5) 33.5%, rgba(${c3},0.156) 50.25%, rgba(${c3},0) 67%),
        radial-gradient(circle at ${b4x + dx4}% ${b4y + dy4}%, rgba(${c4},1) 0%, rgba(${c4},0.844) 10.28%, rgba(${c4},0.5) 20.55%, rgba(${c4},0.156) 30.83%, rgba(${c4},0) 41.1%),
        #161825
      `;
      raf = requestAnimationFrame(render);
    };

    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <div ref={ref} className={`absolute inset-0 ${className}`} style={{ backgroundColor: '#161825' }} aria-hidden="true" />;
}
