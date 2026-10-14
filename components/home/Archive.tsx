"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getLastRead } from "@/lib/saved";

type Card = { date: string; title: string };
type Month = { month: string; items: Card[] };

export function Archive({ months, total }: { months: Month[]; total: number }) {
  const [last, setLast] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  useEffect(() => {
    setLast(getLastRead());
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? months
        .map(({ month, items }) => ({
          month,
          items: items.filter(
            (i) => i.title.toLowerCase().includes(q) || i.date.includes(q),
          ),
        }))
        .filter((m) => m.items.length > 0)
    : months;
  const shown = filtered.reduce((n, m) => n + m.items.length, 0);

  return (
    <section className="archive-all" aria-labelledby="archive-all-h">
      <h2 className="section-label" id="archive-all-h" style={{ marginTop: 48 }}>
        지난 뉴스 모아보기
        <span style={{ fontWeight: 400, color: "var(--color-muted-2)", textTransform: "none", letterSpacing: 0 }}>
          ({total}호)
        </span>
      </h2>
      <div className="archive-search">
        <label htmlFor="archive-q" className="sr-only">
          아카이브 검색
        </label>
        <input
          id="archive-q"
          type="search"
          placeholder="제목이나 날짜로 검색 (예: Gemini, 2026-10-14)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {q ? <span className="archive-search-count">{shown}호</span> : null}
      </div>
      {filtered.length === 0 ? (
        <p className="archive-empty">검색 결과가 없습니다.</p>
      ) : null}
      {filtered.map(({ month, items }) => {
        const [y, m] = month.split("-");
        return (
          <details key={month} className="archive-month" open={month === months[0]?.month}>
            <summary>
              {y}년 {Number(m)}월
              <span>{items.length}호</span>
            </summary>
            <ul className="archive-list">
              {items.map((issue) => (
                <li key={issue.date}>
                  <Link href={`/news/${issue.date}`} className={last === issue.date ? "is-last" : undefined}>
                    <time dateTime={issue.date}>{issue.date}</time>
                    {issue.title}
                    {last === issue.date ? <em className="last-read">읽는 중</em> : null}
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        );
      })}
    </section>
  );
}
