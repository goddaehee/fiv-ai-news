import { ReposCatalog } from "@/components/repos/ReposCatalog";
import { CATALOG, CATALOG_COUNT, deepDiveSlug } from "@/data/catalog";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "유행레포 공부자료 — 5분 AI 뉴스",
  description: "화제가 된 GitHub 오픈소스 프로젝트를 한국어 딥다이브로 정리한 카탈로그.",
};

export default function ReposPage() {
  const deepMap: Record<string, string> = {};
  for (const cat of CATALOG) {
    for (const sub of cat.subs) {
      for (const item of sub.items) {
        const deep = deepDiveSlug(item.slug);
        if (deep) deepMap[item.slug] = deep;
      }
    }
  }

  return <ReposCatalog catalog={CATALOG} catalogCount={CATALOG_COUNT} deepMap={deepMap} />;
}
