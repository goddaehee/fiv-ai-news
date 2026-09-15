const LINES = [
  {
    group: "모양",
    items: [
      { id: "straight", title: "직선", body: "계층이 분명하고 방향이 하나일 때.", d: "M 16 40 H 184" },
      { id: "elbow", title: "꺾인 선", body: "격자에 맞춰 피할 때. 직교 다이어그램의 기본.", d: "M 16 28 H 100 V 52 H 184" },
      { id: "curve", title: "곡선", body: "관계의 흐름을 부드럽게 보여줄 때.", d: "M 16 48 C 70 8, 130 72, 184 24" },
    ],
  },
  {
    group: "질감",
    items: [
      { id: "solid", title: "실선", body: "확정된 의존, 실제 호출.", d: "M 16 40 H 184", dash: "" },
      { id: "dash", title: "점선", body: "선택·예정·약한 결합.", d: "M 16 40 H 184", dash: "6 6" },
      { id: "thick", title: "굵은 선", body: "주 경로. 한 장면에 하나면 충분하다.", d: "M 16 40 H 184", width: 4 },
    ],
  },
  {
    group: "라우팅",
    items: [
      { id: "avoid", title: "장애물 우회", body: "노드를 뚫지 않는다. 먼저 칸을 비운다.", d: "M 16 56 H 70 V 20 H 184" },
      { id: "bundle", title: "묶음", body: "같은 방향 선은 간격을 맞춰 나란히.", d: "M 16 28 H 184 M 16 40 H 184 M 16 52 H 184" },
      { id: "cross", title: "교차 점프", body: "어쩔 수 없이 겹치면 한 쪽만 띄운다.", d: "M 16 40 H 184 M 100 16 V 64" },
    ],
  },
  {
    group: "움직임",
    items: [
      { id: "flow", title: "흐름", body: "데이터가 실제로 이동할 때만 움직인다.", d: "M 16 40 H 184", animate: true },
      { id: "pulse", title: "강조", body: "에러·병목 한 줄만 깜빡이게.", d: "M 16 40 H 184", pulse: true },
      { id: "still", title: "정지", body: "구조 설명은 움직이지 않는 편이 읽힌다.", d: "M 16 40 H 184" },
    ],
  },
] as const;

function LineSvg({
  d,
  dash,
  width,
  animate,
  pulse,
}: {
  d: string;
  dash?: string;
  width?: number;
  animate?: boolean;
  pulse?: boolean;
}) {
  return (
    <svg viewBox="0 0 200 80" className="line-svg" aria-hidden="true">
      <circle cx="16" cy="40" r="5" fill="var(--color-ink)" />
      <circle cx="184" cy="40" r="5" fill="var(--color-accent)" />
      <path
        d={d}
        fill="none"
        stroke="currentColor"
        strokeWidth={width ?? 2}
        strokeDasharray={dash || (animate ? "8 8" : undefined)}
        className={animate ? "line-flow" : pulse ? "line-pulse" : undefined}
      />
    </svg>
  );
}

export function LineCollection() {
  return (
    <article className="diagram-page" id="main-content">
      <p className="issue-eyebrow">다이어그램</p>
      <h1>연결선 컬렉션 — 모양 · 질감 · 라우팅 · 움직임</h1>
      <p className="lede">
        상자는 누구나 그립니다. 읽히는 그림과 안 읽히는 그림은 <strong>선</strong>에서 갈립니다. 네 축만
        정해 두면 아키텍처 스케치가 설명문이 됩니다.
      </p>
      <div className="diagram-answer">
        <b>한 줄 답</b>
        확정은 실선, 미정은 점선, 주 경로는 굵게, 흐름이 있을 때만 움직입니다. 선을 장식하지 마십시오.
      </div>
      {LINES.map((group, i) => (
        <section key={group.group}>
          <h2>
            <span className="num">{String(i + 1).padStart(2, "0")}</span>
            {group.group}
          </h2>
          <div className="diagram-grid">
            {group.items.map((item) => (
              <div className="diagram-card" key={item.id}>
                <LineSvg
                  d={item.d}
                  dash={"dash" in item ? item.dash : undefined}
                  width={"width" in item ? item.width : undefined}
                  animate={"animate" in item ? item.animate : undefined}
                  pulse={"pulse" in item ? item.pulse : undefined}
                />
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            ))}
          </div>
        </section>
      ))}
    </article>
  );
}
