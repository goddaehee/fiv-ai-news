import { Suspense } from "react";
import { Archive } from "@/components/home/Archive";
import { FaqList } from "@/components/home/FaqList";
import { Feed } from "@/components/home/Feed";
import { Hero } from "@/components/home/Hero";
import { KeyStrip } from "@/components/home/KeyStrip";
import { SearchBox } from "@/components/home/SearchBox";
import { SubscribeForm } from "@/components/home/SubscribeForm";
import { ISSUES, citationCount, issuesByMonth, latestIssue } from "@/data/news";
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
  }));
  const repoIndex = REPOS.map((r) => ({
    slug: r.slug,
    name: r.name,
    repo: r.repo,
    oneLiner: r.oneLiner,
    subcategory: r.subcategory,
  }));
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
