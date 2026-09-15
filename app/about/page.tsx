import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "소개 — 5분 AI 뉴스" };

export default function AboutPage() {
  return (
    <main className="prose-page about" id="main-content" tabIndex={-1}>
      <p className="issue-eyebrow">소개</p>
      <h1>5분 AI 뉴스 소개</h1>
      <p className="lede">
        쏟아지는 AI·테크 소식을 매일 아침 <strong>5분 브리핑과 전체 분석</strong>으로 정리해 전하는 한국어
        큐레이션 매체입니다. 남의 글을 모으는 것이 아니라, 하루치 타임라인을 훑고 1차 출처로 교차검증한 뒤
        한국어 맥락과 <strong>시사점·실무 팁</strong>을 더해 다시 씁니다.
      </p>
      <h2>우리가 만드는 것</h2>
      <p>
        매일 아침, 지난 24시간 동안 개발자·연구자·업계가 실제로 주목한 AI/테크 이슈를 그날의 주요 흐름으로
        정리합니다. 모델 릴리스, 정책·규제, 오픈소스, 바이브코딩·개발자 툴, 업계 인사까지 — 흩어진 소식을
        하나의 이야기로 엮습니다. 각 호에는 감정·온도 분석과 바로 써먹을 실무 팁이 붙습니다.
      </p>
      <h2>어떻게 만드나 — 제작 과정</h2>
      <p>핵심은 수집이 아니라 분석과 재구성입니다.</p>
      <ol className="steps">
        <li>
          <b>1. 수집</b>
          X(트위터)와 공식 블로그에서 하루치 AI·테크 게시물을 모읍니다.
        </li>
        <li>
          <b>2. 분석</b>
          키워드 빈도와 토픽을 추려, 그날 실제로 화제가 된 주제를 고릅니다.
        </li>
        <li>
          <b>3. 교차검증</b>
          모델명·수치·발표 내용은 공식 문서와 1차 매체로 다시 확인합니다. 확인되지 않은 수치는 미확정으로
          명시합니다.
        </li>
        <li>
          <b>4. 재구성</b>
          한국어로 다시 쓰고, 각 주제마다 ‘시사점’과 ‘실무 팁’을 더합니다.
        </li>
        <li>
          <b>5. 검증·발행</b>
          과장 표현을 걷어내고(강도는 동사가 아니라 수치로), 원본 링크를 보존한 채 발행합니다.
        </li>
      </ol>
      <h2>편집 원칙</h2>
      <ul>
        <li>
          <strong>1차 출처 우선</strong> — 트윗은 실마리일 뿐, 핵심 사실은 공식 발표·1차 매체로 교차검증합니다.
        </li>
        <li>
          <strong>과장 배제</strong> — ‘혁명’·‘폭발’ 대신 측정된 수치로 강도를 전합니다.
        </li>
        <li>
          <strong>불확실성 표기</strong> — 확인 안 된 루머·수치는 감추지 않고 미확정으로 밝힙니다.
        </li>
        <li>
          <strong>프라이버시 존중</strong> — 개인 식별 정보는 빼고 기술·산업 논의로 정리합니다.
        </li>
        <li>
          <strong>출처 추적성</strong> — 인용한 게시물·문서의 원본 링크를 남겨 직접 확인할 수 있게 합니다.
        </li>
      </ul>
      <h2>사이트에서 제공하는 것</h2>
      <ul>
        <li>
          <strong>매일 아침 뉴스 리포트</strong> —{" "}
          <Link href="/" style={{ color: "var(--color-accent-ink)" }}>
            5분 브리핑과 전체 분석
          </Link>
        </li>
        <li>
          <strong>통합 검색</strong> — 과거 기사 본문과 레포까지 찾아 바로 점프
        </li>
        <li>
          <strong>레포 공부자료</strong> — 화제의 오픈소스 저장소를 같은 틀로 분석
        </li>
        <li>
          <strong>선 컬렉션</strong> — 다이어그램 연결선의 모양·질감·라우팅·움직임
        </li>
        <li>
          <strong>RSS · 사이트맵</strong> — <a href="/feed.xml">feed.xml</a> · <a href="/sitemap.xml">sitemap.xml</a> ·{" "}
          <a href="/llms.txt">llms.txt</a>
        </li>
        <li>
          <strong>테마</strong> — 라이트 · 다크 · 세피아
        </li>
      </ul>
      <p>
        <Link href="/#subscribe-card" className="site-button">
          무료로 구독하기 →
        </Link>
      </p>
      <h2>운영자 · 연락처</h2>
      <dl className="meta-box">
        <dt>매체명</dt>
        <dd>5분 AI 뉴스</dd>
        <dt>운영</dt>
        <dd>개인 운영 · 매일 발행</dd>
        <dt>구독 메일</dt>
        <dd>평일 07:00 전후 · 무료 · 1클릭 해지</dd>
        <dt>개인정보</dt>
        <dd>
          <Link href="/privacy">개인정보처리방침</Link>
        </dd>
      </dl>
      <p style={{ color: "var(--color-muted)", fontSize: 14, marginTop: 24 }}>
        본 사이트의 요약·분석은 트윗 기반 큐레이션 형식을 재현한 것이며, 개별 수치·주장은 원문과 1차 출처를 통한
        추가 확인을 권장합니다. 이 저장소는 원 매체와 무관한 독립 재창작입니다.
      </p>
      <h2>검색·AI 도구로 읽기</h2>
      <p>
        기사의 발행일과 원문 링크를 함께 확인해 주세요. <a href="/feed.xml">RSS</a>,{" "}
        <a href="/sitemap.xml">사이트맵</a>, 선택적 안내문인 <a href="/llms.txt">llms.txt</a>를 제공합니다.
      </p>
    </main>
  );
}
