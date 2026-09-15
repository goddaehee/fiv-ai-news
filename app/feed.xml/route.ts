import { ISSUES } from "@/data/news";
import { rfc822 } from "@/lib/utils";

export const dynamic = "force-static";

const origin = process.env.SITE_ORIGIN || "https://fiv-ai-news.vercel.app";

function esc(s: string) {
  return s.replaceAll("&", "&").replaceAll("<", "<").replaceAll(">", ">");
}

export function GET() {
  const items = ISSUES.map(
    (i) => `    <item>
      <title>${esc(i.title)}</title>
      <link>${origin}/news/${i.date}</link>
      <guid isPermaLink="true">${origin}/news/${i.date}</guid>
      <category>AI · 테크</category>
      <pubDate>${rfc822(i.date)}</pubDate>
      <description><![CDATA[${i.dek}]]></description>
    </item>`,
  ).join("\n");

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>5분 AI 뉴스</title>
    <link>${origin}/</link>
    <description>매일 아침 AI·테크 트렌드를 5분 분량으로 큐레이션합니다.</description>
    <language>ko-KR</language>
    <atom:link href="${origin}/feed.xml" rel="self" type="application/rss+xml"/>
    <lastBuildDate>${rfc822(ISSUES[0].date)}</lastBuildDate>
${items}
  </channel>
</rss>`;

  return new Response(rss, {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
}
