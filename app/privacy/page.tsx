import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "개인정보처리방침 — 5분 AI 뉴스" };

export default function PrivacyPage() {
  return (
    <main className="prose-page legal" id="main-content" tabIndex={-1}>
      <p className="issue-eyebrow">최종 개정일 · 2026-09-15</p>
      <h1>개인정보처리방침</h1>
      <p>
        5분 AI 뉴스(이하 “사이트”)는 방문자의 개인정보를 소중히 다룹니다. 본 방침은 수집·이용 항목, 보관 기간,
        방문자가 행사할 수 있는 권리를 정리한 것입니다.
      </p>
      <h2>1. 수집하는 개인정보 항목</h2>
      <p>
        이 데모가 직접 서버에 저장하는 정보는 없습니다. 구독 폼에 입력한 <strong>이메일 주소</strong>는 방문자의
        브라우저 로컬 스토리지에만 남습니다. 실제 뉴스레터는 발송되지 않습니다.
      </p>
      <ul>
        <li>수집 시점: 구독 폼에서 “구독하기”를 클릭한 시점</li>
        <li>수집 항목: 이메일 주소(기기 내 저장)</li>
        <li>목적: 구독 상태 표시</li>
        <li>보관: 브라우저 데이터를 지우거나 구독을 해제하면 삭제</li>
      </ul>
      <h2>2. 자동 수집 정보</h2>
      <p>테마 선택(라이트/다크/세피아)은 브라우저 로컬 스토리지에 저장됩니다. 광고 식별 쿠키는 사용하지 않습니다.</p>
      <h2>3. 위치·날씨</h2>
      <p>
        이 사이트는 위치 정보를 수집하지 않으며 날씨 API를 호출하지 않습니다. 테마와 구독 상태만 브라우저 저장소에
        남습니다.
      </p>
      <h2>4. 방문자의 권리</h2>
      <ul>
        <li>구독 표시 삭제: 브라우저 저장소를 지우면 즉시 사라집니다.</li>
        <li>테마 초기화: 같은 방법으로 기본 라이트로 돌아갑니다.</li>
      </ul>
      <h2>5. 미성년자</h2>
      <p>사이트는 만 14세 미만의 정보를 의도적으로 수집하지 않습니다.</p>
      <h2>6. 개정 안내</h2>
      <p>본 방침이 바뀌면 이 페이지에 바로 반영하고, 상단의 최종 개정일을 함께 갱신합니다.</p>
      <p style={{ marginTop: 32 }}>
        <Link href="/" style={{ color: "var(--color-accent-ink)", fontWeight: 700 }}>
          ← 홈으로
        </Link>
      </p>
    </main>
  );
}
