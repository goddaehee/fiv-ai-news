"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";

type NewsHit = {
  date: string;
  title: string;
  heroline: string;
  dek: string;
  intro: string;
  briefing: string;
  analysis: string;
};
type RepoHit = {
  slug: string;
  name: string;
  repo: string;
  oneLiner: string;
  subcategory: string;
};

export function SearchBox({ newsIndex, repoIndex }: { newsIndex: NewsHit[]; repoIndex: RepoHit[] }) {
  const [q, setQ] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const fromUrl = params.get("q");
    if (fromUrl && fromUrl.trim().length >= 2) setQ(fromUrl.trim());
  }, [params]);

  const query = [...chips, q.trim()].filter(Boolean).join(" ");

  const results = useMemo(() => {
    const terms = query.toLowerCase().split(/\s+/).filter((t) => t.length >= 1);
    if (query.replace(/\s/g, "").length < 2) return [];
    const news = newsIndex
      .filter((i) => {
        const blob = `${i.title} ${i.heroline} ${i.dek} ${i.intro} ${i.briefing} ${i.analysis}`.toLowerCase();
        return terms.every((t) => blob.includes(t));
      })
      .slice(0, 6)
      .map((h) => ({ kind: "뉴스" as const, title: `${h.date} ${h.title}`, snippet: h.dek, href: `/news/${h.date}` }));
    const repos = repoIndex
      .filter((r) => {
        const blob = `${r.name} ${r.repo} ${r.oneLiner} ${r.subcategory}`.toLowerCase();
        return terms.every((t) => blob.includes(t));
      })
      .slice(0, 4)
      .map((h) => ({ kind: "레포" as const, title: h.name, snippet: h.oneLiner, href: `/repos/${h.slug}` }));
    return [...news, ...repos];
  }, [query, newsIndex, repoIndex]);

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const term = q.trim();
      if (term.length < 2) return;
      if (!chips.includes(term)) setChips((c) => [...c, term]);
      setQ("");
    }
    if (e.key === "Backspace" && !q && chips.length) setChips((c) => c.slice(0, -1));
  };

  return (
    <div className="side-card site-search" id="site-search">
      <div className="section-label">
        <label htmlFor="search-input">기사·레포 검색</label>
      </div>
      <div style={{ position: "relative" }}>
        <input
          id="search-input"
          type="search"
          placeholder="기사 본문 · 레포 검색"
          autoComplete="off"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
        />
      </div>
      {chips.length ? (
        <div className="search-chips">
          {chips.map((c) => (
            <button key={c} type="button" className="search-chip" onClick={() => setChips((all) => all.filter((x) => x !== c))}>
              {c} ×
            </button>
          ))}
          <span className="search-scope">Enter로 조건을 쌓아 좁힙니다</span>
        </div>
      ) : null}
      {query.replace(/\s/g, "").length >= 2 && results.length === 0 ? (
        <div style={{ marginTop: 10, fontSize: 13, color: "var(--color-muted)", textAlign: "center", padding: "12px 0" }}>
          검색 결과 없음
        </div>
      ) : null}
      {results.length > 0 ? (
        <div className="search-results">
          {results.map((r) => (
            <button
              key={r.href + r.title}
              type="button"
              className="search-hit"
              onClick={() => {
                setQ("");
                setChips([]);
                router.push(r.href);
              }}
            >
              <span className="k">{r.kind}</span>
              <span className="t">{r.title}</span>
              <span className="s">{r.snippet}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
