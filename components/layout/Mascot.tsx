"use client";

import { useEffect, useRef } from "react";

export function Mascot() {
  const left = useRef<SVGCircleElement>(null);
  const right = useRef<SVGCircleElement>(null);
  const wrap = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const el = wrap.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = (e.clientX - cx) / 40;
      const dy = (e.clientY - cy) / 40;
      const x = Math.max(-3.2, Math.min(3.2, dx));
      const y = Math.max(-2.4, Math.min(2.4, dy));
      left.current?.setAttribute("transform", `translate(${x} ${y})`);
      right.current?.setAttribute("transform", `translate(${x} ${y})`);
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  return (
    <button
      ref={wrap}
      type="button"
      className="page-mascot"
      aria-label="뉴스 로봇"
      onClick={(e) => {
        const svg = e.currentTarget.querySelector("svg");
        if (!svg) return;
        svg.animate(
          [
            { transform: "scale(1,1)" },
            { transform: "scale(1.08,0.88)" },
            { transform: "scale(1,1)" },
          ],
          { duration: 280, easing: "cubic-bezier(0.22,1,0.36,1)" },
        );
      }}
    >
      <svg viewBox="0 0 72 72" aria-hidden="true">
        <rect x="10" y="16" width="52" height="44" rx="10" fill="var(--color-ink)" />
        <rect x="16" y="24" width="40" height="22" rx="6" fill="var(--color-bg)" />
        <circle ref={left} cx="28" cy="35" r="4.2" fill="var(--color-accent-ink)" />
        <circle ref={right} cx="44" cy="35" r="4.2" fill="var(--color-accent-ink)" />
        <rect x="30" y="50" width="12" height="3" fill="var(--color-bg)" opacity="0.85" />
        <circle cx="36" cy="12" r="3.2" fill="var(--color-accent-ink)" />
        <rect x="35" y="12" width="2" height="6" fill="var(--color-ink)" />
      </svg>
    </button>
  );
}
