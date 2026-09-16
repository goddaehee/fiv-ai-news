"use client";

import { useEffect, useRef, useState } from "react";
import { Moon, Sun, BookOpen } from "lucide-react";
import { useTheme } from "./SiteShell";
import { THEME_LABEL, THEMES, type ThemeName } from "@/lib/theme";

const ICO: Record<ThemeName, typeof Moon> = {
  light: Moon,
  dark: Sun,
  sepia: BookOpen,
};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const Icon = ICO[theme];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="theme-wrap" ref={wrap}>
      <button
        type="button"
        className="theme-toggle"
        aria-label={`테마: ${THEME_LABEL[theme]}. 바꾸려면 누르세요`}
        aria-haspopup="menu"
        aria-expanded={open}
        title={`테마: ${THEME_LABEL[theme]}`}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon size={21} strokeWidth={2} />
      </button>
      {open ? (
        <div className="theme-menu" role="menu">
          {THEMES.map((t) => (
            <button
              key={t}
              type="button"
              role="menuitemradio"
              aria-checked={theme === t}
              className={theme === t ? "on" : undefined}
              onClick={() => {
                setTheme(t);
                setOpen(false);
              }}
            >
              {THEME_LABEL[t]}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
