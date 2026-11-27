import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { AnalysisImage, Issue } from "./types";

export type { Issue };

export const ISSUES: Issue[] = readdirSync(join(process.cwd(), "content/issues"))
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(readFileSync(join(process.cwd(), "content/issues", f), "utf8")) as Issue)
  // P19 이중 방어: draft:true인 호는 발행 확정이 아니므로 공개에서 제외.
  // 파이프라인은 validate 통과 시 draft를 false로 뒤집어 커밋한다(run.py).
  .filter((i) => !i.draft)
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

/**
 * P36 (6라운드 개선 5번): 호 대표 이미지 — 홈 최근 발행 카드 썸네일용.
 * 리드 스토리(브리핑 첫 항목과 1:1인 분석)의 이미지를 우선하고,
 * 없으면 이미지가 있는 첫 분석으로 폴백한다. 이미지가 전혀 없는
 * 호(초기 호들)는 undefined → 카드는 기존 타이포 썸네일을 유지한다.
 */
export function coverImage(issue: Issue): AnalysisImage | undefined {
  const leadId = issue.briefing[0]?.id;
  const lead = issue.analysis.find((a) => a.id === leadId);
  if (lead?.images?.length) return lead.images[0];
  for (const a of issue.analysis) {
    if (a.images?.length) return a.images[0];
  }
  return undefined;
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
