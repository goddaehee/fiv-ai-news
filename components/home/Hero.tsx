"use client";

import { useRouter } from "next/navigation";
import { formatDotDate } from "@/lib/utils";

type Props = {
  date: string;
  tag: string;
  heroline: string;
  dek: string;
  title: string;
  sections: number;
  citations: number;
  readMin: number;
};

export function Hero(issue: Props) {
  const router = useRouter();
  return (
    <>
      <div className="section-label">오늘의 브리핑</div>
      <button type="button" className="hero" onClick={() => router.push(`/news/${issue.date}`)}>
        <div className="hero-copy">
          <div className="hero-meta">
            <span className="hero-badge">톱뉴스</span>
            <span className="topbar-date">{formatDotDate(issue.date)}</span>
            <span className="fc-dot" />
            <span className="topbar-date">{issue.tag}</span>
          </div>
          <h1>{issue.heroline}</h1>
          <p className="hero-dek">{issue.dek}</p>
          <div className="hero-action">
            5분 브리핑 읽기 <span>→</span>
          </div>
          <div className="hero-stats">
            <div>
              <div className="stat-val">{issue.sections}</div>
              <div className="stat-label">섹션</div>
            </div>
            <div>
              <div className="stat-val">{issue.citations}</div>
              <div className="stat-label">인용</div>
            </div>
            <div>
              <div className="stat-val">{issue.readMin}분</div>
              <div className="stat-label">전체 분석</div>
            </div>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="hero-cover">
            <div className="hc-top">
              <span className="hc-eyebrow">DAILY BRIEF</span>
              <span className="hc-date">{formatDotDate(issue.date)}</span>
            </div>
            <div className="hc-mark">
              5분 AI<span className="hc-dot">.</span>
            </div>
            <div className="hc-rule" />
            <div className="hc-tag">{issue.title}</div>
          </div>
        </div>
      </button>
    </>
  );
}
