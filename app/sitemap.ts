import type { MetadataRoute } from "next";
import { ISSUES } from "@/data/news";
import { REPOS } from "@/data/repos";

const origin = process.env.SITE_ORIGIN || "https://fiv-ai-news.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticPaths = ["", "/about", "/privacy", "/repos", "/diagram"];
  return [
    ...staticPaths.map((p) => ({ url: `${origin}${p || "/"}`, changeFrequency: "daily" as const })),
    ...ISSUES.map((i) => ({ url: `${origin}/news/${i.date}`, changeFrequency: "weekly" as const })),
    ...REPOS.map((r) => ({ url: `${origin}/repos/${r.slug}`, changeFrequency: "monthly" as const })),
  ];
}
