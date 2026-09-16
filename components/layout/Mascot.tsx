import { useEffect, useRef } from "react";

const DIRECTIONS = ["up-left", "up", "up-right", "left", "center", "right", "down-left", "down", "down-right"] as const;
const REACTIONS = ["blink", "heart", "sparkle", "surprised", "wink", "bashful", "sleepy", "dizzy", "delighted"] as const;
const CLOCKWISE = ["right", "down-right", "down", "down-left", "left", "up-left", "up", "up-right"] as const;
const SECTOR = (Math.PI * 2) / CLOCKWISE.length;
const HYSTERESIS = 0.12;
const PAYOFFS = ["heart", "sparkle", "delighted"] as const;

function cell(index: number) {
  return `${(index % 3) * 50}% ${Math.floor(index / 3) * 50}%`;
}

function wrap(angle: number) {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

function matches(query: string) {
  return typeof window !== "undefined" && window.matchMedia?.(query).matches;
}

export function Mascot() {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const squashRef = useRef<HTMLSpanElement>(null);
  const dirRef = useRef<HTMLSpanElement>(null);
  const reactRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const button = buttonRef.current;
    const squash = squashRef.current;
    const dirLayer = dirRef.current;
    const reactLayer = reactRef.current;
    if (!button || !squash || !dirLayer || !reactLayer) return;

    let direction: (typeof DIRECTIONS)[number] = "center";
    let reaction: (typeof REACTIONS)[number] | null = null;
    const timers: number[] = [];
    const boops = { count: 0, at: 0 };

    const render = () => {
      dirLayer.style.backgroundPosition = cell(DIRECTIONS.indexOf(direction));
      dirLayer.style.opacity = reaction ? "0" : "1";
      reactLayer.style.backgroundPosition = cell(REACTIONS.indexOf(reaction || "blink"));
      reactLayer.style.opacity = reaction ? "1" : "0";
    };

    const setDirection = (next: (typeof DIRECTIONS)[number]) => {
      if (next === direction) return;
      direction = next;
      render();
    };

    const setReaction = (next: (typeof REACTIONS)[number] | null) => {
      reaction = next;
      render();
    };

    let sector = -1;
    let pointer: { x: number; y: number } | null = null;
    let frame = 0;

    const aim = () => {
      frame = 0;
      if (!pointer) return;
      const box = button.getBoundingClientRect();
      const dx = pointer.x - (box.left + box.width / 2);
      const dy = pointer.y - (box.top + box.height / 2);
      if (Math.hypot(dx, dy) < box.width / 2) {
        sector = -1;
        setDirection("center");
        return;
      }
      const angle = Math.atan2(dy, dx);
      if (sector !== -1 && Math.abs(wrap(angle - sector * SECTOR)) < SECTOR / 2 + HYSTERESIS) {
        return;
      }
      sector = (Math.round(angle / SECTOR) + CLOCKWISE.length) % CLOCKWISE.length;
      setDirection(CLOCKWISE[sector]);
    };

    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(aim);
    };

    const onMove = (event: PointerEvent) => {
      pointer = { x: event.clientX, y: event.clientY };
      schedule();
    };

    const hoverOk = matches("(hover: hover) and (pointer: fine)");
    if (hoverOk) {
      window.addEventListener("pointermove", onMove, { passive: true });
      window.addEventListener("scroll", schedule, { passive: true });
    }

    const onClick = () => {
      timers.forEach((id) => window.clearTimeout(id));
      timers.length = 0;
      const later = (ms: number, next: (typeof REACTIONS)[number] | null) => {
        timers.push(window.setTimeout(() => setReaction(next), ms));
      };
      const now = Date.now();
      boops.count = now - boops.at < 1600 ? boops.count + 1 : 1;
      boops.at = now;
      if (boops.count >= 4) {
        boops.count = 0;
        setReaction("dizzy");
        later(1100, null);
      } else {
        setReaction("blink");
        later(120, PAYOFFS[(boops.count - 1) % PAYOFFS.length]);
        later(560, null);
      }
      if (matches("(prefers-reduced-motion: reduce)") || !squash.animate) return;
      squash.animate(
        [
          { transform: "scale(1, 1)", easing: "ease-in" },
          { transform: "scale(1.10, 0.86)", offset: 0.18, easing: "ease-out" },
          { transform: "scale(0.95, 1.08)", offset: 0.45, easing: "ease-in-out" },
          { transform: "scale(1.03, 0.97)", offset: 0.72, easing: "ease-in-out" },
          { transform: "scale(1, 1)" },
        ],
        { duration: 420, easing: "linear" },
      );
    };

    button.addEventListener("click", onClick);
    render();

    return () => {
      timers.forEach((id) => window.clearTimeout(id));
      button.removeEventListener("click", onClick);
      if (hoverOk) {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("scroll", schedule);
      }
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <button
      ref={buttonRef}
      type="button"
      className="page-mascot"
      data-page-mascot
      aria-label="뉴스 로봇 콕 찌르기"
    >
      <span className="pm-squash" ref={squashRef}>
        <span
          ref={dirRef}
          className="pm-layer pm-dir"
          style={{ backgroundImage: "url(/assets/mascot/newsbot-directions.webp)" }}
        />
        <span
          ref={reactRef}
          className="pm-layer pm-react"
          style={{ backgroundImage: "url(/assets/mascot/newsbot-reactions.webp)" }}
        />
      </span>
    </button>
  );
}
