"use client";

import { useEffect, useRef } from "react";

export function AnimatedGradient({ className = "" }: { className?: string }) {
  const fieldRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const field = fieldRef.current;
    if (!field) return;
    const blobs = Array.from(field.querySelectorAll<HTMLElement>(".gradient-blob"));
    let frame = 0;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = performance.now();
    const render = (now: number) => {
      const t = (now - start) / 1000;
      blobs.forEach((blob, index) => {
        const driftX = Math.sin(t * [.22,.18,.16,.2][index] + index * 1.7) * [34,28,24,20][index];
        const driftY = Math.cos(t * [.17,.21,.19,.15][index] + index) * [26,32,20,24][index];
        blob.style.transform = `translate3d(${driftX}px,${driftY}px,0)`;
      });
      if (!reduced) frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => cancelAnimationFrame(frame);
  }, []);

  return <div ref={fieldRef} className={`animated-gradient ${className}`} aria-hidden="true"><i className="gradient-blob blob-one"/><i className="gradient-blob blob-two"/><i className="gradient-blob blob-three"/><i className="gradient-blob blob-four"/></div>;
}
