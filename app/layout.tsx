import type { Metadata } from "next";
import Script from "next/script";
import { SiteShell } from "@/components/layout/SiteShell";
import { latestIssue } from "@/data/news";
import "./globals.css";

const THEME_BOOT =
  "(function(){try{var t=localStorage.getItem('fiv-theme');if(t==='dark'||t==='sepia'||t==='light'){document.documentElement.setAttribute('data-theme',t);}else{document.documentElement.setAttribute('data-theme','light');}}catch(e){document.documentElement.setAttribute('data-theme','light');}})();";

export const metadata: Metadata = {
  metadataBase: new URL("https://fiv-ai-news.vercel.app"),
  title: "5분 AI 뉴스 — 데일리 AI·테크 트렌드 리포트",
  description: "매일 아침 5분, 엄선된 AI·테크 트렌드 리포트.",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "5분 AI 뉴스 — 데일리 AI·테크 트렌드 리포트",
    description: "매일 아침 5분, 엄선된 AI·테크 트렌드 리포트.",
    locale: "ko_KR",
    type: "website",
    siteName: "5분 AI 뉴스",
  },
  alternates: {
    types: {
      "application/rss+xml": "/feed.xml",
    },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const latest = latestIssue();
  return (
    <html lang="ko" suppressHydrationWarning>
      <body>
        <Script id="theme-boot" strategy="beforeInteractive">
          {THEME_BOOT}
        </Script>
        <SiteShell latestDate={latest.date} latestTitle={latest.title} latestHeroline={latest.heroline}>
          {children}
        </SiteShell>
      </body>
    </html>
  );
}
