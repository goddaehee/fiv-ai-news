"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CatalogCat } from "@/data/catalog";
import { getInterest, listSavedRepos, setInterest, toggleSavedRepo } from "@/lib/saved";
import { allTokensIn, tokenize } from "@/lib/search";

type DeepMap = Record<string, string>;

export function ReposCatalog({
  catalog,
  catalogCount,
  deepMap,
}: {
  catalog: CatalogCat[];
  catalogCount: number;
  deepMap: DeepMap;
  categories?: unknown;
  repos?: unknown;
}) {
  const [q, setQ] = useState("");
  const [savedOnly, setSavedOnly] = useState(false);
  const [minStar, setMinStar] = useState(0);
  const [tag, setTag] = useState("");
  const [saved, setSaved] = useState<string[]>([]);
  const [interest, setInt] = useState<Record<string, number>>({});

  useEffect(() => {
    setSaved(listSavedRepos());
    const map: Record<string, number> = {};
    for (const cat of catalog) {
      for (const sub of cat.subs) {
        for (const item of sub.items) {
          const lv = getInterest(item.slug);
          if (lv) map[item.slug] = lv;
        }
      }
    }
    setInt(map);
  }, [catalog]);

  const tokens = tokenize(q);

  const visible = useMemo(() => {
    return catalog.map((cat) => {
      const subs = cat.subs.map((sub) => {
        const items = sub.items.filter((item) => {
          if (savedOnly && !saved.includes(item.slug)) return false;
          if (minStar && (interest[item.slug] ?? 0) < minStar) return false;
          if (tag && !(item.tags ?? []).includes(tag)) return false;
          if (!tokens.length) return true;
          const blob = `${item.name} ${item.one ?? ""} ${item.use ?? ""} ${(item.tags ?? []).join(" ")} ${sub.title} ${cat.title}`.toLowerCase();
          return allTokensIn(blob, tokens);
        });
        const ranked = [...items].sort((a, b) => {
          const fa = saved.includes(a.slug) ? 1 : 0;
          const fb = saved.includes(b.slug) ? 1 : 0;
          if (fa !== fb) return fb - fa;
          return (interest[b.slug] ?? 0) - (interest[a.slug] ?? 0);
        });
        return { ...sub, items: ranked };
      });
      return { ...cat, subs: subs.filter((s) => s.items.length) };
    }).filter((c) => c.subs.length);
  }, [catalog, tokens, savedOnly, minStar, tag, saved, interest]);

  const shown = visible.reduce((n, c) => n + c.subs.reduce((m, s) => m + s.items.length, 0), 0);
  const filtering = Boolean(q.trim() || savedOnly || minStar || tag);

  const reset = () => {
    setQ("");
    setSavedOnly(false);
    setMinStar(0);
    setTag("");
  };

  return (
    <main id="main-content" tabIndex={-1}>
      <div className="repo-mast" id="masthead">
        <p className="kicker">
          <Link href="/" style={{ color: "inherit" }}>
            ← 5분 AI 뉴스
          </Link>
        </p>
        <h1>유행레포 공부자료</h1>
        <p className="repo-stats">
          <b>{catalogCount}</b>개 레포 · <b>{catalog.length}</b>개 카테고리 · 갱신 2026-09-07 · 출처 TrendShift
        </p>
        <input
          id="q"
          type="search"
          value={q}
          onChange={(e) => {
            setTag("");
            setQ(e.target.value);
          }}
          placeholder="레포 이름·설명으로 검색…"
          autoComplete="off"
          spellCheck={false}
          className="repo-search"
        />
        <nav className="chips repo-chips" aria-label="카테고리">
          <button type="button" className="chip on" onClick={reset}>
            전체<span className="chip-n">{catalogCount}</span>
          </button>
          <button
            type="button"
            className={savedOnly ? "chip chip-fav on" : "chip chip-fav"}
            aria-pressed={savedOnly}
            onClick={() => setSavedOnly((v) => !v)}
          >
            ▱ 저장한 자료<span className="chip-n">{saved.length}</span>
          </button>
          {catalog.map((c) => (
            <a key={c.title} className="chip" href={`#${c.id ?? c.title}`}>
              {c.emo} {c.title}
              <span className="chip-n">{c.subs.reduce((n, s) => n + s.items.length, 0)}</span>
            </a>
          ))}
        </nav>
        <div className="filter-bar" aria-label="관심도 필터">
          <span className="fb-label">관심도 필터</span>
          <span className="fb-stars">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                className={minStar >= n ? "fstar is-selected" : "fstar"}
                aria-label={`관심도 ${n} 이상`}
                aria-pressed={minStar === n}
                onClick={() => setMinStar((cur) => (cur === n ? 0 : n))}
              >
                ★
              </button>
            ))}
          </span>
        </div>
      </div>

      <div className="catalog-results">
        <span>
          {shown}개 자료{filtering ? ` · 전체 ${catalogCount}개 중` : ""}
          {tag ? ` · 태그 #${tag}` : ""}
        </span>
        {filtering ? (
          <button type="button" className="catalog-reset" onClick={reset}>
            검색·필터 초기화
          </button>
        ) : null}
      </div>

      {shown === 0 ? (
        <div className="catalog-empty">
          <strong>찾는 자료가 없어요.</strong>
          <p>검색어를 짧게 바꾸거나 저장·관심도 필터를 해제해 보세요.</p>
          <button type="button" className="catalog-reset" onClick={reset}>
            전체 자료 다시 보기
          </button>
        </div>
      ) : (
        <div className="cats">
          {visible.map((cat) => (
            <section className="cat" id={cat.id ?? cat.title} key={cat.title} style={{ ["--cat-accent" as string]: cat.accent }}>
              <div className="cathead">
                <span className="emo">{cat.emo}</span>
                <h2>{cat.title}</h2>
                <span className="cnt">
                  {cat.subs.reduce((n, s) => n + s.items.length, 0)}
                  {filtering ? `/${cat.subs.reduce((n, s) => n + s.items.length, 0)}` : ""}
                </span>
              </div>
              {cat.subs.map((sub, si) => (
                <div className="sub" key={sub.title}>
                  {sub.title ? (
                    <div className="subhead">
                      <span className="sub-mark">{String(si + 1).padStart(2, "0")}</span>
                      <h3>{sub.title}</h3>
                      <span className="sub-n">{sub.items.length}</span>
                    </div>
                  ) : null}
                  <div className="grid">
                    {sub.items.map((item, i) => {
                      const deep = deepMap[item.slug];
                      const href = `/repos/${deep ?? item.slug}`;
                      const fav = saved.includes(item.slug);
                      const lv = interest[item.slug] ?? 0;
                      return (
                        <article className={fav ? "card is-fav" : "card"} key={item.slug} data-name={item.name}>
                          <Link className="c-open" href={href} aria-label={`${item.name} 공부자료 열기`} />
                          <div className="c-top">
                            <button
                              type="button"
                              className={fav ? "c-fav on" : "c-fav"}
                              aria-pressed={fav}
                              title="저장 (위로 고정)"
                              onClick={() => {
                                const on = toggleSavedRepo(item.slug);
                                setSaved(listSavedRepos());
                                void on;
                              }}
                            >
                              <span aria-hidden="true">▱</span> 저장
                            </button>
                          </div>
                          <span className="c-idx">{String(i + 1).padStart(2, "0")}</span>
                          <Link className="c-name" href={href} style={deep ? { fontWeight: 800 } : undefined}>
                            {item.name}
                          </Link>
                          {item.tags?.length ? (
                            <span className="c-tags">
                              {item.tags.map((t) => (
                                <button
                                  key={t}
                                  type="button"
                                  className={tag === t ? "tag on" : "tag"}
                                  onClick={() => setTag((cur) => (cur === t ? "" : t))}
                                >
                                  {t}
                                </button>
                              ))}
                            </span>
                          ) : null}
                          <span className="c-one">{item.use || item.one}</span>
                          <div className="c-meta">
                            <span className="c-interest" title="관심도">
                              <span className="ilabel">관심도</span>
                              {[1, 2, 3, 4, 5].map((n) => (
                                <button
                                  key={n}
                                  type="button"
                                  className={lv >= n ? "star is-selected" : "star"}
                                  aria-label={`관심도 ${n}`}
                                  onClick={() => {
                                    const next = setInterest(item.slug, n);
                                    setInt((m) => ({ ...m, [item.slug]: next }));
                                  }}
                                >
                                  ★
                                </button>
                              ))}
                            </span>
                            {item.gh ? (
                              <a className="c-github" href={item.gh} target="_blank" rel="noopener noreferrer">
                                GitHub ↗
                              </a>
                            ) : null}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </div>
              ))}
            </section>
          ))}
        </div>
      )}

      <section className="repos-all" id="repos-all" aria-labelledby="repos-all-h">
        <h2 id="repos-all-h">
          전체 딥다이브 목록 <span>({catalogCount}편)</span>
        </h2>
        <p className="repos-all-note">위 카드와 같은 자료를 분류별 글 목록으로 모았습니다. 검색·필터 없이 훑어보거나 링크를 공유할 때 씁니다.</p>
        {catalog.map((c) => (
          <details key={c.title} className="repos-all-cat" id={c.id ? `all-${c.id}` : undefined}>
            <summary>
              {c.emo} {c.title}
              <span>{c.subs.reduce((n, s) => n + s.items.length, 0)}편</span>
            </summary>
            {c.subs.map((s) => (
              <div key={s.title}>
                <h3>{s.title}</h3>
                <ul>
                  {s.items.map((item) => {
                    const deep = deepMap[item.slug];
                    return (
                      <li key={item.slug}>
                        <Link href={`/repos/${deep ?? item.slug}`} style={deep ? { fontWeight: 800 } : undefined}>
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
