"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { RepoCategory } from "@/data/types";
import type { CatalogCat } from "@/data/catalog";

type Cat = { id: RepoCategory | "all"; label: string };
type Card = {
  slug: string;
  name: string;
  repo: string;
  category: RepoCategory;
  subcategory: string;
  oneLiner: string;
  stars: string;
  license: string;
};

export function ReposCatalog({
  categories,
  repos,
  catalog,
  catalogCount,
  deepMap,
}: {
  categories: Cat[];
  repos: Card[];
  catalog: CatalogCat[];
  catalogCount: number;
  deepMap: Record<string, string>;
}) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<RepoCategory | "all">("all");

  const list = useMemo(() => {
    const terms = q.toLowerCase().trim();
    return repos.filter((r) => {
      if (cat !== "all" && r.category !== cat) return false;
      if (!terms) return true;
      const blob = `${r.name} ${r.repo} ${r.oneLiner} ${r.subcategory}`.toLowerCase();
      return blob.includes(terms);
    });
  }, [q, cat, repos]);

  const filteredCatalog = useMemo(() => {
    const terms = q.toLowerCase().trim();
    if (!terms) return catalog;
    return catalog
      .map((c) => ({
        ...c,
        subs: c.subs
          .map((s) => ({
            ...s,
            items: s.items.filter(
              (i) => i.name.toLowerCase().includes(terms) || i.slug.toLowerCase().includes(terms),
            ),
          }))
          .filter((s) => s.items.length),
      }))
      .filter((c) => c.subs.length);
  }, [q, catalog]);

  return (
    <main id="main-content" tabIndex={-1}>
      <div className="repo-mast">
        <p className="kicker">
          <Link href="/" style={{ color: "inherit" }}>
            ← 5분 AI 뉴스
          </Link>
        </p>
        <h1>유행레포 공부자료</h1>
        <p className="repo-stats">
          <b>{catalogCount}</b>개 레포 · <b>{catalog.length}</b>개 카테고리 · 한국어 딥다이브 <b>{repos.length}</b>편 ·
          갱신 2026-09-16
        </p>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="레포 이름·설명으로 검색…"
          autoComplete="off"
          className="repo-search"
        />
        <div className="chips" role="tablist" aria-label="카테고리">
          {categories.map((c) => (
            <button
              key={c.id}
              type="button"
              className={cat === c.id ? "chip on" : "chip"}
              onClick={() => setCat(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>
      <div className="repo-grid">
        {list.map((r) => (
          <Link key={r.slug} href={`/repos/${r.slug}`} className="repo-card">
            <div className="cat">{r.subcategory}</div>
            <h3>{r.name}</h3>
            <p>{r.oneLiner}</p>
            <div className="meta">
              {r.repo} · ★ {r.stars} · {r.license}
            </div>
          </Link>
        ))}
      </div>
      {list.length === 0 ? (
        <p style={{ textAlign: "center", color: "var(--color-muted)", padding: 40 }}>검색 결과 없음</p>
      ) : null}

      <section className="repos-all" id="repos-all" aria-labelledby="repos-all-h">
        <h2 id="repos-all-h">
          전체 목록 <span>({catalogCount}편)</span>
        </h2>
        <p className="repos-all-note">
          위 카드와 같은 자료를 분류별 글 목록으로 모았습니다. 굵은 항목은 이 클론에서 한국어 본문을 읽을 수 있습니다.
        </p>
        {filteredCatalog.map((c) => (
          <details key={c.title} className="repos-all-cat">
            <summary>
              {c.title}
              <span>{c.subs.reduce((n, s) => n + s.items.length, 0)}편</span>
            </summary>
            {c.subs.map((s) => (
              <div key={s.title}>
                <h3>{s.title}</h3>
                <ul>
                  {s.items.map((item) => {
                    const deep = deepMap[item.slug];
                    const href = `/repos/${deep ?? item.slug}`;
                    return (
                      <li key={item.slug}>
                        <Link href={href} style={deep ? { fontWeight: 800 } : undefined}>
                          {item.name}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </details>
        ))}
      </section>
    </main>
  );
}
