import Link from "next/link";
import { notFound } from "next/navigation";
import { RepoDeepDive } from "@/components/repos/RepoDeepDive";
import { REPOS, getRepo } from "@/data/repos";
import type { Metadata } from "next";

export function generateStaticParams() {
  return REPOS.map((r) => ({ slug: r.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const repo = getRepo(slug);
  if (!repo) return { title: "레포 공부 — 5분 AI 뉴스" };
  return { title: `${repo.name} 딥다이브 — 5분 AI 뉴스`, description: repo.oneLiner };
}

export default async function RepoPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const repo = getRepo(slug);
  if (!repo) notFound();
  return (
    <main id="main-content" tabIndex={-1}>
      <RepoDeepDive repo={repo} />
      <p style={{ textAlign: "center", padding: "24px 0 80px" }}>
        <Link href="/repos" style={{ color: "var(--color-accent-ink)", fontWeight: 700 }}>
          카탈로그로 돌아가기 →
        </Link>
      </p>
    </main>
  );
}
