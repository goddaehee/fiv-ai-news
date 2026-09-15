import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Issue } from "./types";

export type { Issue };

export const ISSUES: Issue[] = readdirSync(join(process.cwd(), "content/issues"))
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(readFileSync(join(process.cwd(), "content/issues", f), "utf8")) as Issue)
  .sort((a, b) => b.date.localeCompare(a.date));

export function getIssue(date: string) {
  return ISSUES.find((i) => i.date === date);
}

export function latestIssue() {
  return ISSUES[0];
}

export function citationCount(issue: Issue) {
  return issue.analysis.reduce((n, a) => n + a.sources.length, 0);
}

export function neighbors(date: string) {
  const i = ISSUES.findIndex((n) => n.date === date);
  return {
    newer: i > 0 ? ISSUES[i - 1] : undefined,
    older: i >= 0 && i < ISSUES.length - 1 ? ISSUES[i + 1] : undefined,
  };
}

export function issuesByMonth() {
  const map = new Map<string, Issue[]>();
  for (const issue of ISSUES) {
    const key = issue.date.slice(0, 7);
    const list = map.get(key) ?? [];
    list.push(issue);
    map.set(key, list);
  }
  return [...map.entries()].map(([month, items]) => ({ month, items }));
}

export function searchNews(q: string) {
  const terms = q.toLowerCase().split(/\s+/).map((t) => t.trim()).filter(Boolean);
  if (!terms.length) return [];
  const hits: { date: string; title: string; snippet: string; href: string }[] = [];
  for (const issue of ISSUES) {
    const blob = [
      issue.title,
      issue.heroline,
      issue.dek,
      issue.intro,
      ...issue.briefing.map((b) => `${b.headline} ${b.summary}`),
      ...issue.analysis.map((a) => `${a.title} ${a.body.join(" ")} ${a.takeaway}`),
    ]
      .join("\n")
      .toLowerCase();
    if (terms.every((t) => blob.includes(t))) {
      hits.push({
        date: issue.date,
        title: `${issue.date} ${issue.title}`,
        snippet: issue.dek,
        href: `/news/${issue.date}`,
      });
    }
  }
  return hits;
}
