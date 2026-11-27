"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { formatDotDate } from "@/lib/utils";

type Card = {
  date: string;
  title: string;
  heroline: string;
  dek: string;
  tag: string;
  readMin: number;
  /** P36: 호 대표 이미지 (리드 분석 일러스트). 없으면 타이포 썸네일. */
  thumb?: { src: string; alt: string };
};

/**
 * P36 (6라운드 개선 5번): 카드 썸네일.
 * 대표 이미지가 있으면 이미지를 채우고 날짜만 칩으로 얹어 호마다
 * 얼굴이 달라지게 한다. 이미지가 없거나 로드에 실패하면 기존의
 * 검은 타이포 썸네일(날짜+헤로라인)로 폴백해 어색하지 않게 유지한다.
 */
function CardThumb({ issue }: { issue: Card }) {
  const [imgOk, setImgOk] = useState(true);
  if (issue.thumb && imgOk) {
    return (
      <div className="fc-thumb">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          className="fc-img"
          src={issue.thumb.src}
          alt={issue.thumb.alt}
          loading="lazy"
          onError={() => setImgOk(false)}
        />
        <div className="fc-hd fc-hd-chip">{formatDotDate(issue.date)}</div>
      </div>
    );
  }
  return (
    <div className="fc-thumb">
      <div className="fc-hd">{formatDotDate(issue.date)}</div>
      <div className="fc-hl">{issue.heroline}</div>
    </div>
  );
}

export function Feed({ issues }: { issues: Card[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const rest = issues.slice(1);
  const shown = open ? rest : rest.slice(0, 6);
  return (
    <section id="feed">
      <div className="section-label" style={{ marginTop: 48 }}>
        최근 발행
      </div>
      <div className="feed">
        {shown.map((issue) => (
          <button
            key={issue.date}
            type="button"
            className="feed-card"
            onClick={() => router.push(`/news/${issue.date}`)}
          >
            <CardThumb issue={issue} />
            <div className="fc-content">
              <div className="fc-meta">
                <span>{issue.date}</span>
                <span className="fc-dot" />
                <span>{issue.tag}</span>
              </div>
              <h3 className="fc-title">{issue.title}</h3>
              <p className="fc-dek">{issue.dek}</p>
              <div className="fc-foot">{issue.readMin} MIN</div>
            </div>
          </button>
        ))}
      </div>
      {rest.length > 6 ? (
        <div className="feed-more-wrap">
          <button type="button" className="feed-more" onClick={() => setOpen((v) => !v)}>
            {open ? "접기" : `지난 호 더 보기 · ${rest.length - 6}건`}
          </button>
        </div>
      ) : null}
    </section>
  );
}
