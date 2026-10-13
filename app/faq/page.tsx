import Link from "next/link";
import type { Metadata } from "next";
import { FaqList } from "@/components/home/FaqList";

export const metadata: Metadata = {
  title: "자주 묻는 질문 | 5분 AI 뉴스",
  description: "5분 AI 뉴스의 발행 주기, 구독·해지 방법 등 자주 묻는 질문 모음입니다.",
  alternates: { canonical: "/faq" },
};

export default function FaqPage() {
  return (
    <main className="prose-page faq" id="main-content" tabIndex={-1}>
      <h1 className="sr-only">자주 묻는 질문</h1>
      <p className="page-back">
        <Link href="/">← 홈으로</Link>
      </p>
      <FaqList />
    </main>
  );
}
