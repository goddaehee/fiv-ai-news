export type ThemeName = "light" | "dark" | "sepia";

export const THEME_KEY = "fiv-theme";
export const THEMES: ThemeName[] = ["light", "dark", "sepia"];

export function readTheme(): ThemeName {
  if (typeof window === "undefined") return "light";
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "sepia" || saved === "light") return saved;
  } catch {
    /* ignore */
  }
  return "light";
}

export function applyTheme(theme: ThemeName) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  document.body.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* ignore */
  }
}

export function nextTheme(current: ThemeName): ThemeName {
  const i = THEMES.indexOf(current);
  return THEMES[(i + 1) % THEMES.length] ?? "light";
}

export const THEME_LABEL: Record<ThemeName, string> = {
  light: "라이트",
  dark: "다크",
  sepia: "세피아",
};
