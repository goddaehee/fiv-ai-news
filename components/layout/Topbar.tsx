"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mascot } from "./Mascot";
import { ThemeToggle } from "./ThemeToggle";
import { formatDotWeek } from "@/lib/utils";

const NAV = [
  { href: "/", label: "뉴스", match: "home" },
  { href: "/#feed", label: "지난 발행", match: "feed" },
  { href: "/repos", label: "레포 공부", match: "repos" },
  { href: "/diagram", label: "선 컬렉션", match: "diagram" },
  { href: "/about", label: "소개", match: "about" },
  { href: "/#subscribe-card", label: "구독", match: "sub" },
] as const;

export function Topbar({
  latestDate,
  latestTitle,
  latestHeroline,
}: {
  latestDate: string;
  latestTitle: string;
  latestHeroline: string;
}) {
  const pathname = usePathname();

  return (
    <header className="topbar">
      <div className="utility-bar">
        <div className="utility-inner">
          <div>
            <span>최신 호</span>
            <span className="utility-sep" />
            <span>5분 에디션</span>
          </div>
          <div className="utility-center">매일 아침, AI·테크 흐름을 한국어로 압축.</div>
          <div className="utility-links">
            <Link href="/privacy">개인정보</Link>
            <Link href="/about">문의</Link>
            <span aria-hidden="true">×</span>
          </div>
        </div>
      </div>
      <div className="topbar-inner">
        <div className="brand-row">
          <Mascot />
          <Link href="/" className="brand">
            <div className="brand-mark">
              5분 AI<span className="accent">.</span>
            </div>
            <div className="brand-sub">매일 아침 5분 AI·테크 브리프</div>
          </Link>
        </div>
        <nav className="nav" aria-label="주요 탐색">
          {NAV.map((item) => {
            const active =
              (item.match === "home" && pathname === "/") ||
              (item.match === "repos" && pathname.startsWith("/repos")) ||
              (item.match === "diagram" && pathname.startsWith("/diagram")) ||
              (item.match === "about" && pathname === "/about");
            return (
              <Link key={item.label} href={item.href} className={active ? "active" : undefined}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="topbar-actions">
          <ThemeToggle />
          <div className="topbar-date">{formatDotWeek(latestDate)}</div>
        </div>
      </div>
      <div className="signal-strip">
        <div className="signal-strip-inner">
          <span className="ticker-pill">최신</span>
          <div className="ticker-copy">
            <strong>{latestDate}</strong> · {latestHeroline} — {latestTitle}
          </div>
          <Link href={`/news/${latestDate}`} className="ticker-link">
            리포트 보기 →
          </Link>
        </div>
      </div>
    </header>
  );
}
