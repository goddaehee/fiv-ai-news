import { Suspense } from "react";
import { Archive } from "@/components/home/Archive";
import { FaqList } from "@/components/home/FaqList";
import { Feed } from "@/components/home/Feed";
import { Hero } from "@/components/home/Hero";
import { KeyStrip } from "@/components/home/KeyStrip";
import { SearchBox } from "@/components/home/SearchBox";
import { SubscribeForm } from "@/components/home/SubscribeForm";
import { ISSUES, citationCount, issuesByMonth, latestIssue } from "@/data/news";
import { CATALOG, deepDiveSlug } from "@/data/catalog";
import { REPOS } from "@/data/repos";

export default function HomePage() {
  const latest = latestIssue();
  const newsIndex = ISSUES.map((i) => ({
    date: i.date,
    title: i.title,
    heroline: i.heroline,
    dek: i.dek,
    intro: i.intro,
    briefing: i.briefing.map((b) => `${b.headline} ${b.summary}`).join(" "),
    analysis: i.analysis.map((a) => `${a.title} ${a.takeaway}`).join(" "),
    sections: [
      ...i.briefing.map((b) => ({ id: b.id, title: b.headline, text: b.summary })),
      ...i.analysis.map((a) => ({ id: a.id, title: a.title, text: `${a.bullets.join(" ")} ${a.body.join(" ")} ${a.takeaway}` })),
    ],
  }));
  const repoIndex = [
    ...REPOS.map((r) => ({
      slug: r.slug,
      name: r.name,
      repo: r.repo,
      oneLiner: r.oneLiner,
      subcategory: r.subcategory,
    })),
    ...CATALOG.flatMap((c) =>
      c.subs.flatMap((s) =>
        s.items
          .filter((item) => !deepDiveSlug(item.slug))
          .map((item) => ({
            slug: item.slug,
            name: item.name,
            repo: item.gh ?? item.name,
            oneLiner: item.use || item.one || s.title,
            subcategory: s.title,
          })),
      ),
    ),
  ];
  return (
    <main className="main" id="main-content" tabIndex={-1}>
      <Suspense fallback={null}>
        <SearchBox newsIndex={newsIndex} repoIndex={repoIndex} />
      </Suspense>
      <Hero
        date={latest.date}
        tag={latest.tag}
        heroline={latest.heroline}
        dek={latest.dek}
        title={latest.title}
        sections={latest.briefing.length}
        citations={citationCount(latest)}
        readMin={latest.readMin}
      />
      <KeyStrip />
      <SubscribeForm />
      <Feed issues={ISSUES.map((i) => ({ date: i.date, title: i.title, heroline: i.heroline, dek: i.dek, tag: i.tag, readMin: i.readMin }))} />
      <Archive
        total={ISSUES.length}
        months={issuesByMonth().map(({ month, items }) => ({
          month,
          items: items.map((i) => ({ date: i.date, title: i.title })),
        }))}
      />
      <FaqList />
      <p className="sr-only">최신 호 {latest.date}</p>
    </main>
  );
}
