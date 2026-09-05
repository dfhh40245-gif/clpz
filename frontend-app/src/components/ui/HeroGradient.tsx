import { useEffect, useRef } from 'react';

/**
 * CLPZ animated hero gradient — amber/gold blobs drifting on dark canvas.
 * Pure CSS radial-gradients updated via rAF, no WebGL needed.
 */
export default function HeroGradient({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf: number;
    const start = performance.now();

    // Phase offsets for each blob
    const p1 = 0, p2 = 2.1, p3 = 4.2;
    // Base positions (%)
    const b1x = 65, b1y = 40;
    const b2x = 25, b2y = 70;
    const b3x = 50, b3y = 15;

    const render = (now: number) => {
      const t = (now - start) / 1000;
      const ph = t * 0.7;

      const dx1 = (Math.sin(ph * 0.55 + p1) - Math.sin(p1)) * 12;
      const dy1 = (Math.sin(ph * 0.43 + p1 * 1.3) - Math.sin(p1 * 1.3)) * 12;
      const dx2 = (Math.sin(ph * 0.55 + p2) - Math.sin(p2)) * 12;
      const dy2 = (Math.sin(ph * 0.43 + p2 * 1.3) - Math.sin(p2 * 1.3)) * 12;
      const dx3 = (Math.sin(ph * 0.55 + p3) - Math.sin(p3)) * 12;
      const dy3 = (Math.sin(ph * 0.43 + p3 * 1.3) - Math.sin(p3 * 1.3)) * 12;

      // CLPZ amber palette: warm amber, deep gold, subtle warm white
      el.style.background = `
        radial-gradient(circle at ${b1x + dx1}% ${b1y + dy1}%, rgba(240,160,48,0.15) 0%, rgba(240,160,48,0.08) 20%, rgba(240,160,48,0) 45%),
        radial-gradient(circle at ${b2x + dx2}% ${b2y + dy2}%, rgba(212,138,32,0.12) 0%, rgba(212,138,32,0.06) 22%, rgba(212,138,32,0) 48%),
        radial-gradient(circle at ${b3x + dx3}% ${b3y + dy3}%, rgba(245,179,77,0.08) 0%, rgba(245,179,77,0.04) 18%, rgba(245,179,77,0) 42%),
        #0a0a0b
      `;
      raf = requestAnimationFrame(render);
    };

    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      ref={ref}
      className={`absolute inset-0 ${className}`}
      style={{ backgroundColor: '#0a0a0b' }}
      aria-hidden="true"
    />
  );
}
