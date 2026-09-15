import Link from "next/link";

export function Footer() {
  return (
    <footer className="site-footer">
      <div>
        <div className="footer-brand">
          5분 AI<span>.</span>
        </div>
        <p>매일 아침, X 타임라인의 AI·테크 소식을 한국어로 다시 쓰는 5분 브리프.</p>
        <small>© 5분 AI 뉴스 · 원문 저작권은 각 작성자에게 있습니다.</small>
      </div>
      <nav>
        <strong>읽기</strong>
        <Link href="/">오늘의 브리핑</Link>
        <Link href="/#archive-all-h">지난 뉴스</Link>
        <Link href="/repos">레포 공부</Link>
        <Link href="/diagram">선 컬렉션</Link>
      </nav>
      <nav>
        <strong>안내</strong>
        <Link href="/about">소개 · 제작 방식</Link>
        <Link href="/privacy">개인정보처리방침</Link>
        <Link href="/#faq">FAQ</Link>
      </nav>
      <nav>
        <strong>구독</strong>
        <Link href="/#subscribe-card">메일 구독</Link>
        <a href="/feed.xml">RSS</a>
        <span>웹은 매일 · 메일은 평일 07:00</span>
        <span>무료 · 1클릭 해지</span>
      </nav>
    </footer>
  );
}
