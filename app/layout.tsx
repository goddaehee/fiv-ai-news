import type { Metadata } from "next";
import { SiteShell } from "@/components/layout/SiteShell";
import { latestIssue } from "@/data/news";
import "./globals.css";

export const metadata: Metadata = {
  title: "5분 AI 뉴스 — 데일리 AI·테크 트렌드 리포트",
  description: "매일 아침 5분, 엄선된 AI·테크 트렌드 리포트.",
  icons: { icon: "/favicon.svg" },
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
        <SiteShell latestDate={latest.date} latestTitle={latest.title} latestHeroline={latest.heroline}>
          {children}
        </SiteShell>
      </body>
    </html>
  );
}
