import { useEffect, useRef } from 'react';

/**
 * CLPZ PipoGradient — light mode animated gradient.
 * Exact Qelvra animation pattern, amber palette.
 */
export default function PipoGradient({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf: number;
    const start = performance.now();

    const p1 = 0, p2 = 2.1, p3 = 4.2;
    const b1x = 68.1, b1y = 46.03;
    const b2x = 25.17, b2y = 75.99;
    const b3x = 53.11, b3y = 12.71;

    const render = (now: number) => {
      const t = (now - start) / 1000;
      const ph = t * 0.86;
      const amt = 0.72;

      const dx1 = (Math.sin(ph * 0.55 + p1) - Math.sin(p1)) * 14 * amt;
      const dy1 = (Math.sin(ph * 0.43 + p1 * 1.3) - Math.sin(p1 * 1.3)) * 14 * amt;
      const dx2 = (Math.sin(ph * 0.55 + p2) - Math.sin(p2)) * 14 * amt;
      const dy2 = (Math.sin(ph * 0.43 + p2 * 1.3) - Math.sin(p2 * 1.3)) * 14 * amt;
      const dx3 = (Math.sin(ph * 0.55 + p3) - Math.sin(p3)) * 14 * amt;
      const dy3 = (Math.sin(ph * 0.43 + p3 * 1.3) - Math.sin(p3 * 1.3)) * 14 * amt;

      el.style.background = `
        radial-gradient(circle at ${b1x + dx1}% ${b1y + dy1}%, rgba(240,160,48,1) 0%, rgba(240,160,48,0.844) 10.28%, rgba(240,160,48,0.5) 20.55%, rgba(240,160,48,0.156) 30.83%, rgba(240,160,48,0) 41.1%),
        radial-gradient(circle at ${b2x + dx2}% ${b2y + dy2}%, rgba(212,138,32,1) 0%, rgba(212,138,32,0.844) 11.15%, rgba(212,138,32,0.5) 22.3%, rgba(212,138,32,0.156) 33.45%, rgba(212,138,32,0) 44.6%),
        radial-gradient(circle at ${b3x + dx3}% ${b3y + dy3}%, rgba(250,249,239,1) 0%, rgba(250,249,239,0.844) 16.66%, rgba(250,249,239,0.5) 33.33%, rgba(250,249,239,0.156) 49.99%, rgba(250,249,239,0) 66.65%),
        #FAF9EF
      `;
      raf = requestAnimationFrame(render);
    };

    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <div ref={ref} className={`absolute inset-0 ${className}`} style={{ backgroundColor: '#FAF9EF' }} aria-hidden="true" />;
}
