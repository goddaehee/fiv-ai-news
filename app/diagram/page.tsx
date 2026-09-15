import { LineCollection } from "@/components/diagram/LineCollection";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "다이어그램 연결선 컬렉션 — 5분 AI 뉴스",
  description: "모양·질감·라우팅·움직임, 읽히는 연결선 컬렉션.",
};

export default function DiagramPage() {
  return (
    <main>
      <LineCollection />
    </main>
  );
}
