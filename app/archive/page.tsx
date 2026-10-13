import Link from "next/link";
import type { Metadata } from "next";
import { Archive } from "@/components/home/Archive";
import { ISSUES, issuesByMonth } from "@/data/news";

export const metadata: Metadata = {
  title: "지난 뉴스 모아보기 | 5분 AI 뉴스",
  description: "5분 AI 뉴스의 지난 호 아카이브. 날짜별로 발행된 모든 브리핑을 모아봅니다.",
  alternates: { canonical: "/archive" },
};

export default function ArchivePage() {
  const months = issuesByMonth().map(({ month, items }) => ({
    month,
    items: items.map((i) => ({ date: i.date, title: i.title })),
  }));
  return (
    <main className="prose-page archive" id="main-content" tabIndex={-1}>
      <h1 className="sr-only">지난 뉴스 아카이브</h1>
      <p className="page-back">
        <Link href="/">← 홈으로</Link>
      </p>
      <Archive total={ISSUES.length} months={months} />
    </main>
  );
}
