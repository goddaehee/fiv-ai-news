import { notFound } from "next/navigation";
import { ArticleView } from "@/components/news/ArticleView";
import { ISSUES, getIssue, neighbors } from "@/data/news";
import type { Metadata } from "next";

export function generateStaticParams() {
  return ISSUES.map((i) => ({ date: i.date }));
}

export async function generateMetadata({ params }: { params: Promise<{ date: string }> }): Promise<Metadata> {
  const { date } = await params;
  const issue = getIssue(date);
  if (!issue) return { title: "5분 AI 뉴스" };
  return {
    title: `${issue.heroline} — ${issue.date} | 5분 AI 뉴스`,
    description: issue.dek,
    openGraph: {
      title: `${issue.heroline} — ${issue.date}`,
      description: issue.dek,
      type: "article",
      locale: "ko_KR",
    },
  };
}

export default async function NewsPage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const issue = getIssue(date);
  if (!issue) notFound();
  const { newer, older } = neighbors(date);
  return (
    <main id="main-content" tabIndex={-1}>
      <ArticleView
        issue={issue}
        newer={newer ? { date: newer.date, title: newer.title } : undefined}
        older={older ? { date: older.date, title: older.title } : undefined}
      />
    </main>
  );
}
