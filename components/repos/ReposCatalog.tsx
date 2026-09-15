"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { RepoCategory } from "@/data/types";

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

export function ReposCatalog({ categories, repos }: { categories: Cat[]; repos: Card[] }) {
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
          <b>{repos.length}</b>개 레포 · <b>{categories.length - 1}</b>개 카테고리 · 같은 틀의 한국어 딥다이브
        </p>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="레포 이름·설명으로 검색…"
          autoComplete="off"
          style={{
            width: "100%",
            font: "inherit",
            padding: "12px 14px",
            border: "1px solid var(--color-ink)",
            background: "var(--color-surface)",
            color: "var(--color-fg)",
          }}
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
    </main>
  );
}
