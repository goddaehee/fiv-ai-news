"use client";

import { Moon, Sun, BookOpen } from "lucide-react";
import { useTheme } from "./SiteShell";
import { THEME_LABEL, nextTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const nxt = nextTheme(theme);
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`${THEME_LABEL[nxt]} 모드로 전환`}
      title={`테마: ${THEME_LABEL[theme]} → ${THEME_LABEL[nxt]}`}
      onClick={() => setTheme(nxt)}
    >
      {theme === "dark" ? (
        <Sun size={21} strokeWidth={2} />
      ) : theme === "sepia" ? (
        <BookOpen size={21} strokeWidth={2} />
      ) : (
        <Moon size={21} strokeWidth={2} />
      )}
    </button>
  );
}
