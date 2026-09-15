import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Repo, RepoCategory } from "./types";

export type { Repo, RepoCategory };

export const CATEGORIES: { id: RepoCategory | "all"; label: string }[] = [
  { id: "all", label: "전체" },
  { id: "agents", label: "에이전트" },
  { id: "skills", label: "스킬·플러그인" },
  { id: "cli", label: "코딩 CLI" },
  { id: "local", label: "로컬 추론" },
  { id: "mcp", label: "MCP·도구" },
  { id: "web", label: "웹·앱" },
];

export const REPOS: Repo[] = readdirSync(join(process.cwd(), "content/repos"))
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(readFileSync(join(process.cwd(), "content/repos", f), "utf8")) as Repo)
  .sort((a, b) => a.trendRank - b.trendRank);

export function getRepo(slug: string) {
  return REPOS.find((r) => r.slug === slug);
}

export function searchRepos(q: string) {
  const terms = q.toLowerCase().split(/\s+/).map((t) => t.trim()).filter(Boolean);
  if (!terms.length) return [];
  return REPOS.filter((r) => {
    const blob = `${r.name} ${r.repo} ${r.oneLiner} ${r.why} ${r.subcategory}`.toLowerCase();
    return terms.every((t) => blob.includes(t));
  }).map((r) => ({
    title: r.name,
    snippet: r.oneLiner,
    href: `/repos/${r.slug}`,
  }));
}
