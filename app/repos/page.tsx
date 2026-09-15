import { ReposCatalog } from "@/components/repos/ReposCatalog";
import { CATEGORIES, REPOS } from "@/data/repos";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "유행레포 공부자료 — 5분 AI 뉴스",
  description: "화제가 된 GitHub 오픈소스 프로젝트를 한국어 딥다이브로 정리한 카탈로그.",
};

export default function ReposPage() {
  return (
    <ReposCatalog
      categories={CATEGORIES}
      repos={REPOS.map((r) => ({
        slug: r.slug,
        name: r.name,
        repo: r.repo,
        category: r.category,
        subcategory: r.subcategory,
        oneLiner: r.oneLiner,
        stars: r.stars,
        license: r.license,
      }))}
    />
  );
}
