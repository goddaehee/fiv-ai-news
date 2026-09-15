import { latestIssue } from "@/data/news";

export function KeyStrip() {
  const issue = latestIssue();
  const shown = issue.keynums.slice(0, 3);
  if (!shown.length) return null;
  return (
    <section className="home-keynums" aria-labelledby="home-keynums-h">
      <h2 id="home-keynums-h">숫자로 읽는 오늘</h2>
      <div className="keynum home-keynum">
        {shown.map((k) => (
          <div className="kn-cell" key={k.lab}>
            <div className="kn-val">{k.val}</div>
            <div className="kn-lab">{k.lab}</div>
            <div className="kn-sub">{k.sub}</div>
          </div>
        ))}
      </div>
      <p className="home-keynums-note">수치의 조건과 출처는 리포트에서 확인하세요.</p>
    </section>
  );
}
