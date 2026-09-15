import Link from "next/link";

export default function NotFound() {
  return (
    <main className="prose-page" id="main-content">
      <h1>해당 호를 찾을 수 없습니다</h1>
      <p>주소의 날짜를 확인해 주세요.</p>
      <p>
        <Link href="/#archive-all-h">지난 뉴스 모아보기 →</Link>
      </p>
    </main>
  );
}
