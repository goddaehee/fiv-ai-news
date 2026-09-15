"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Topbar } from "./Topbar";
import { Footer } from "./Footer";
import { applyTheme, readTheme, type ThemeName } from "@/lib/theme";

const ThemeCtx = createContext<{
  theme: ThemeName;
  setTheme: (t: ThemeName) => void;
}>({ theme: "light", setTheme: () => {} });

export function useTheme() {
  return useContext(ThemeCtx);
}

export function SiteShell({
  children,
  latestDate,
  latestTitle,
  latestHeroline,
}: {
  children: ReactNode;
  latestDate: string;
  latestTitle: string;
  latestHeroline: string;
}) {
  const [theme, setThemeState] = useState<ThemeName>("light");

  useEffect(() => {
    const t = readTheme();
    setThemeState(t);
    applyTheme(t);
  }, []);

  const setTheme = (t: ThemeName) => {
    setThemeState(t);
    applyTheme(t);
  };

  const value = useMemo(() => ({ theme, setTheme }), [theme]);

  return (
    <ThemeCtx.Provider value={value}>
      <a className="skip-link" href="#main-content">
        본문으로 바로가기
      </a>
      <Topbar latestDate={latestDate} latestTitle={latestTitle} latestHeroline={latestHeroline} />
      {children}
      <Footer />
    </ThemeCtx.Provider>
  );
}
