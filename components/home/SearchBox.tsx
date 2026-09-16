"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { allTokensIn, highlightTerms, tokenize } from "@/lib/search";

type Section = { id: string; title: string; text: string };
type NewsHit = {
  date: string;
  title: string;
  heroline: string;
  dek: string;
  intro: string;
  briefing: string;
  analysis: string;
  sections?: Section[];
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
  const [active, setActive] = useState(-1);
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const fromUrl = params.get("q");
    if (fromUrl && fromUrl.trim().length >= 2) setQ(fromUrl.trim());
  }, [params]);

  const query = [...chips, q.trim()].filter(Boolean).join(" ");
  const tokens = tokenize(query);

  const results = useMemo(() => {
    if (query.replace(/\s/g, "").length < 2) return [];
    const news: {
      kind: "뉴스";
      title: string;
      snippet: string;
      href: string;
      sec?: string;
    }[] = [];
    for (const i of newsIndex) {
      let best: { href: string; snippet: string; sec?: string } | null = null;
      for (const sec of i.sections ?? []) {
        const blob = `${sec.title} ${sec.text}`.toLowerCase();
        if (!allTokensIn(blob, tokens)) continue;
        best = {
          href: `/news/${i.date}#sec-${sec.id}`,
          snippet: sec.text.slice(0, 140),
          sec: sec.title.replace(/^\d+\.\s*/, ""),
        };
        break;
      }
      if (!best) {
        const blob = `${i.title} ${i.heroline} ${i.dek} ${i.intro} ${i.briefing} ${i.analysis}`.toLowerCase();
        if (allTokensIn(blob, tokens)) {
          best = { href: `/news/${i.date}`, snippet: i.dek };
        }
      }
      if (best) {
        news.push({ kind: "뉴스", title: `${i.date} ${i.title}`, ...best });
      }
      if (news.length >= 6) break;
    }
    const repos = repoIndex
      .filter((r) => allTokensIn(`${r.name} ${r.repo} ${r.oneLiner} ${r.subcategory}`.toLowerCase(), tokens))
      .slice(0, 4)
      .map((h) => ({ kind: "레포" as const, title: h.name, snippet: h.oneLiner, href: `/repos/${h.slug}`, sec: undefined as string | undefined }));
    return [...news, ...repos];
  }, [query, tokens, newsIndex, repoIndex]);

  const go = (href: string) => {
    setQ("");
    setChips([]);
    setActive(-1);
    router.push(href);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!results.length) return;
      e.preventDefault();
      setActive((i) => {
        const next = e.key === "ArrowDown" ? i + 1 : i - 1;
        if (next < 0) return results.length - 1;
        if (next >= results.length) return 0;
        return next;
      });
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (e.shiftKey) {
        const term = q.trim();
        if (term.length >= 2 && !chips.includes(term)) {
          setChips((c) => [...c, term]);
          setQ("");
        }
        return;
      }
      if (active >= 0 && results[active]) {
        go(results[active].href);
        return;
      }
      if (results[0]) go(results[0].href);
      return;
    }
    if (e.key === "Backspace" && !q && chips.length) setChips((c) => c.slice(0, -1));
    if (e.key === "Escape") {
      setQ("");
      setChips([]);
      setActive(-1);
    }
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
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={results.length > 0}
          aria-controls="search-listbox"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setActive(-1);
          }}
          onKeyDown={onKey}
        />
        {q || chips.length ? (
          <button
            type="button"
            className="search-clear"
            aria-label="검색어 지우기"
            onClick={() => {
              setQ("");
              setChips([]);
              setActive(-1);
            }}
          >
            ×
          </button>
        ) : null}
      </div>
      <p id="search-help" className="sr-only">
        위아래 화살표로 결과를 고르고 Enter로 엽니다. Shift+Enter는 지금 검색어를 고정하고 그 결과 안에서 다시 찾습니다.
      </p>
      {chips.length ? (
        <div className="search-chips">
          {chips.map((c) => (
            <button key={c} type="button" className="search-chip" onClick={() => setChips((all) => all.filter((x) => x !== c))}>
              {c} ×
            </button>
          ))}
          <span className="search-scope">이 결과 안에서 다시 찾습니다</span>
        </div>
      ) : null}
      {q.trim().length >= 2 ? (
        <div className="search-meta-row">
          <button
            type="button"
            className="search-refine"
            title="Shift+Enter"
            onClick={() => {
              const term = q.trim();
              if (term.length >= 2 && !chips.includes(term)) {
                setChips((c) => [...c, term]);
                setQ("");
              }
            }}
          >
            이 결과 안에서 좁히기
          </button>
        </div>
      ) : null}
      {query.replace(/\s/g, "").length >= 2 && results.length === 0 ? (
        <div id="search-empty" style={{ marginTop: 10, fontSize: 13, color: "var(--color-muted)", textAlign: "center", padding: "12px 0" }}>
          검색 결과 없음
        </div>
      ) : null}
      {results.length > 0 ? (
        <div className="search-results" id="search-listbox" role="listbox">
          {results.map((r, i) => (
            <button
              key={r.href + r.title}
              type="button"
              className="search-hit search-opt"
              role="option"
              aria-selected={i === active}
              onClick={() => go(r.href)}
            >
              <span className="k">{r.kind}</span>
              <span className="t">
                {highlightTerms(r.title, tokens).map((p, idx) =>
                  p.hit ? (
                    <mark className="search-mark" key={idx}>
                      {p.t}
                    </mark>
                  ) : (
                    <span key={idx}>{p.t}</span>
                  ),
                )}
              </span>
              {r.sec ? <span className="search-sec">▸ {r.sec}</span> : null}
              <span className="s">{r.snippet}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
