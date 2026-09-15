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
};

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
            <div className="fc-thumb">
              <div className="fc-hd">{formatDotDate(issue.date)}</div>
              <div className="fc-hl">{issue.heroline}</div>
            </div>
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
