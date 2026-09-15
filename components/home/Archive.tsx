import Link from "next/link";
import { ISSUES, issuesByMonth } from "@/data/news";

export function Archive() {
  const months = issuesByMonth();
  return (
    <section className="archive-all" aria-labelledby="archive-all-h">
      <h2 className="section-label" id="archive-all-h" style={{ marginTop: 48 }}>
        지난 뉴스 모아보기
        <span style={{ fontWeight: 400, color: "var(--color-muted-2)", textTransform: "none", letterSpacing: 0 }}>
          ({ISSUES.length}호)
        </span>
      </h2>
      {months.map(({ month, items }) => {
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
                  <Link href={`/news/${issue.date}`}>
                    <time dateTime={issue.date}>{issue.date}</time>
                    {issue.title}
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
