export function Welcome() {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-copy">
        <p className="welcome-eyebrow">처음이어도 괜찮아요</p>
        <p className="welcome-title" id="welcome-title">
          AI 소식, 매일 쉽게.
        </p>
        <p className="welcome-description">
          무슨 일이 생겼는지부터 배경과 조건까지.
          <br />
          중요한 AI 소식을 한국어로 차근차근 읽어요.
        </p>
      </div>
      <div className="welcome-guide">
        <p className="welcome-guide-label">내 속도에 맞게 읽어요</p>
        <ol className="welcome-steps">
          <li>
            <span className="welcome-step-num" aria-hidden="true">
              01
            </span>
            <div>
              <strong>먼저, 핵심 브리핑</strong>
              <span className="welcome-step-desc">
                오늘의 흐름을 짧게 훑어요.
              </span>
            </div>
          </li>
          <li>
            <span className="welcome-step-num" aria-hidden="true">
              02
            </span>
            <div>
              <strong>관심 있는 주제만 깊게</strong>
              <span className="welcome-step-desc">
                배경과 달라지는 점을 읽어요.
              </span>
            </div>
          </li>
          <li>
            <span className="welcome-step-num" aria-hidden="true">
              03
            </span>
            <div>
              <strong>조건과 원문까지 확인</strong>
              <span className="welcome-step-desc">
                발표자의 주장과 한계를 살펴봐요.
              </span>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}
