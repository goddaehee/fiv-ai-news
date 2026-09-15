"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Issue, SourceKind } from "@/data/types";
import { formatDotWeek } from "@/lib/utils";
import { SubscribeForm } from "@/components/home/SubscribeForm";

const KIND: Record<SourceKind, string> = {
  hot: "🔥",
  talk: "💬",
  rt: "🔁",
  doc: "📄",
};

export function ArticleView({
  issue,
  newer,
  older,
}: {
  issue: Issue;
  newer?: { date: string; title: string };
  older?: { date: string; title: string };
}) {
  const [progress, setProgress] = useState(0);
  const firstId = issue.analysis[0]?.id ?? issue.briefing[0]?.id;
  const analysisIds = new Set(issue.analysis.map((a) => a.id));

  useEffect(() => {
    const onScroll = () => {
      const el = document.documentElement;
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? (el.scrollTop / max) * 100 : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [issue.date]);

  return (
    <article className="prose-page">
      <div className="read-rail" style={{ width: `${progress}%` }} />
      <p className="issue-eyebrow">
        오늘의 AI 브리핑 · <time dateTime={issue.date}>{formatDotWeek(issue.date)}</time>
      </p>
      <h1>{issue.heroline}</h1>

      <section className="news-brief" id="brief" aria-labelledby="brief-heading">
        <div className="brief-top">
          <h2 id="brief-heading">5분 브리핑</h2>
          <span>
            약 {issue.briefMin}분 · {issue.briefing.length}개 흐름 (전체 분석 {issue.readMin}분)
          </span>
        </div>
        <p className="brief-intro">핵심만 먼저 읽고, 궁금한 소식은 본문으로 이어 보세요. 화살표가 없는 항목은 브리핑만 있습니다.</p>
        {firstId ? (
          <a className="brief-jump" href={`#sec-${firstId}`}>
            전체 분석 {issue.readMin}분으로 바로 가기 ↓
          </a>
        ) : null}
        <ol className="brief-list">
          {issue.briefing.map((item) => {
            const hasBody = analysisIds.has(item.id);
            return (
              <li key={item.id}>
                {hasBody ? (
                  <a href={`#sec-${item.id}`}>
                    {item.headline} <span aria-hidden="true">↗</span>
                  </a>
                ) : (
                  <strong>
                    {item.headline} <span className="brief-only">브리핑</span>
                  </strong>
                )}
                <p>{item.summary}</p>
              </li>
            );
          })}
        </ol>
        <div className="brief-end">
          <strong>오늘의 브리핑은 여기까지.</strong>
          {firstId ? (
            <a className="site-button" href={`#sec-${firstId}`}>
              전체 분석 {issue.readMin}분 읽기 ↓
            </a>
          ) : null}
          <a href="#subscribe">다음 브리핑 메일로 받기 ↓</a>
        </div>
      </section>

      <div className="key-box">
        <p>
          <strong>주요 키워드</strong>
          <span>{issue.keywords.join(" · ")}</span>
        </p>
        <p>
          <strong>메인 이벤트</strong>
          <span>{issue.mainEvent}</span>
        </p>
      </div>

      <div className="keynum">
        {issue.keynums.map((k) => (
          <div className="kn-cell" key={k.lab}>
            <div className="kn-val">{k.val}</div>
            <div className="kn-lab">{k.lab}</div>
            <div className="kn-sub">{k.sub}</div>
          </div>
        ))}
      </div>

      <p className="issue-intro">{issue.intro}</p>

      <div className="timeline">
        {issue.timeline.map((t) => (
          <div className="tl-item" key={t.t + t.d}>
            <div className="tl-label">{t.t}</div>
            <div className="tl-desc">{t.d}</div>
          </div>
        ))}
      </div>

      <hr className="hr" />

      {issue.analysis.map((sec, idx) => (
        <section className="article-sec" id={`sec-${sec.id}`} key={sec.id}>
          <h2>{sec.title.startsWith(`${idx + 1}.`) ? sec.title : `${idx + 1}. ${sec.title}`}</h2>
          <ul>
            {sec.bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          {sec.body.map((p) => (
            <p key={p.slice(0, 24)}>{p}</p>
          ))}
          {sec.extra ? <p>{sec.extra}</p> : null}
          <blockquote className="bq-take">
            <p>
              <strong>시사점:</strong> {sec.takeaway}
            </p>
            <p>
              <code>#{sec.tags.join(" #")}</code>
            </p>
          </blockquote>
          <p className="src-row">
            <span className="src-lab">출처 {sec.sources.length}</span>
            {sec.sources.map((s) => (
              <a key={s.url + s.handle} href={s.url} target="_blank" rel="noopener noreferrer">
                {KIND[s.kind]} {s.handle}
              </a>
            ))}
          </p>
          <hr className="hr" />
        </section>
      ))}

      <section className="article-sec" id="mood">
        <h2>오늘의 감정·온도</h2>
        <div className="gauge-rows">
          <div className="grow">
            <span className="gdot" style={{ background: "#4773c0" }} />
            <div>
              <b>전환</b> — {issue.mood.shift}
            </div>
          </div>
          <div className="grow">
            <span className="gdot" style={{ background: "#3a9d63" }} />
            <div>
              <b>성장</b> — {issue.mood.grow}
            </div>
          </div>
          <div className="grow">
            <span className="gdot" style={{ background: "#d99a2b" }} />
            <div>
              <b>주의</b> — {issue.mood.caution}
            </div>
          </div>
          <div className="grow">
            <span className="gdot" style={{ background: "#d3543f" }} />
            <div>
              <b>과열</b> — {issue.mood.heat}
            </div>
          </div>
        </div>
      </section>

      <hr className="hr" />

      <section className="article-sec" id="tips">
        <h2>오늘의 실무 팁</h2>
        {issue.tips.map((tip, i) => (
          <p key={tip.title}>
            <strong>
              {i + 1}. {tip.title}
            </strong>
            <br />
            {tip.body} — ({tip.via})
          </p>
        ))}
      </section>

      <hr className="hr" />
      <p>
        <strong>확인 방식</strong>
      </p>
      <p>{issue.method}</p>
      <p>
        <strong>라벨 가이드</strong> — 📄 공식 문서 · 🔥 널리 퍼진 글 · 💬 댓글이 붙은 글 · 🔁 재확산 비중이 높은 글
      </p>

      <aside className="reader-subscribe" id="subscribe">
        <p className="issue-eyebrow">내일 아침에도</p>
        <p className="reader-subscribe-title">AI 흐름을 메일함에서 이어 보세요.</p>
        <p>무료 이메일 구독 · 언제든 해지할 수 있어요. 이 데모는 브라우저에만 저장합니다.</p>
        <SubscribeForm compact />
      </aside>

      <nav className="prevnext" aria-label="다른 호 둘러보기">
        {older ? (
          <Link href={`/news/${older.date}`}>
            <span className="k">← 이전 호</span>
            <span>{older.title}</span>
          </Link>
        ) : (
          <span />
        )}
        {newer ? (
          <Link href={`/news/${newer.date}`}>
            <span className="k">다음 호 →</span>
            <span>{newer.title}</span>
          </Link>
        ) : null}
      </nav>
      <p style={{ textAlign: "center", marginTop: 24, fontSize: 13 }}>
        <Link href="/#archive-all-h" style={{ color: "var(--color-muted)", textDecoration: "none" }}>
          전체 아카이브 보기 (지난 호 전체) →
        </Link>
      </p>
    </article>
  );
}
