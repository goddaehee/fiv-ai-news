import Link from "next/link";
import { notFound } from "next/navigation";
import { CatalogStub } from "@/components/repos/CatalogStub";
import { RepoDeepDive } from "@/components/repos/RepoDeepDive";
import { allCatalogSlugs, deepDiveSlug, findCatalogItem } from "@/data/catalog";
import { REPOS, getRepo } from "@/data/repos";
import type { Metadata } from "next";

export const dynamicParams = true;

export function generateStaticParams() {
  const slugs = new Set([...REPOS.map((r) => r.slug), ...allCatalogSlugs()]);
  return [...slugs].map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const mapped = deepDiveSlug(slug) ?? slug;
  const repo = getRepo(mapped);
  if (repo) return { title: `${repo.name} 딥다이브 — 5분 AI 뉴스`, description: repo.oneLiner };
  const catalog = findCatalogItem(slug);
  if (catalog) return { title: `${catalog.name} — 레포 공부`, description: catalog.name };
  return { title: "레포 공부 — 5분 AI 뉴스" };
}

export default async function RepoPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const mapped = deepDiveSlug(slug) ?? slug;
  const repo = getRepo(mapped);
  if (repo) {
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
  const catalog = findCatalogItem(slug);
  if (!catalog) notFound();
  return (
    <main id="main-content" tabIndex={-1}>
      <CatalogStub
        name={catalog.name}
        slug={catalog.slug}
        category={catalog.category}
        subcategory={catalog.subcategory}
        one={catalog.one}
        use={catalog.use}
        gh={catalog.gh}
        tags={catalog.tags}
      />
    </main>
  );
}
