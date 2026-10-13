import catalog from "../content/repos-catalog.json";
import { REPOS } from "./repos";
import { allTokensIn, tokenize } from "@/lib/search";

export type CatalogCard = {
  slug: string;
  name: string;
  one?: string;
  use?: string;
  gh?: string;
  tags?: string[];
  href?: string;
};
export type CatalogSub = { title: string; items: CatalogCard[] };
export type CatalogCat = {
  id?: string;
  emo?: string;
  accent?: string;
  title: string;
  count?: string;
  subs: CatalogSub[];
};

export const CATALOG: CatalogCat[] = catalog as CatalogCat[];

export const CATALOG_COUNT = CATALOG.reduce(
  (n, cat) => n + cat.subs.reduce((m, s) => m + s.items.length, 0),
  0,
);

const SLUG_ALIAS: Record<string, string> = {
  "anthropics-skills": "anthropic-skills",
  "aaif-goose-goose": "goose",
  "llama.cpp": "llama-cpp",
  CopilotKit: "copilotkit",
};

const DEEP_SLUGS = new Set(REPOS.map((r) => r.slug));

export function deepDiveSlug(catalogSlug: string) {
  const aliased = SLUG_ALIAS[catalogSlug] ?? catalogSlug;
  return DEEP_SLUGS.has(aliased) ? aliased : null;
}

export function findCatalogItem(slug: string) {
  for (const cat of CATALOG) {
    for (const sub of cat.subs) {
      for (const item of sub.items) {
        if (item.slug === slug || item.name === slug) {
          return { ...item, category: cat.title, subcategory: sub.title };
        }
      }
    }
  }
  return undefined;
}

export function allCatalogSlugs() {
  const out: string[] = [];
  for (const cat of CATALOG) {
    for (const sub of cat.subs) {
      for (const item of sub.items) out.push(item.slug);
    }
  }
  return out;
}

export function githubSearch(name: string) {
  return `https://github.com/search?q=${encodeURIComponent(name)}&type=repositories`;
}

export function searchCatalog(q: string) {
  const tokens = tokenize(q);
  if (!tokens.length) return [];
  const hits: { title: string; snippet: string; href: string }[] = [];
  for (const cat of CATALOG) {
    for (const sub of cat.subs) {
      for (const item of sub.items) {
        const blob = `${item.name} ${item.one ?? ""} ${item.use ?? ""} ${(item.tags ?? []).join(" ")} ${sub.title} ${cat.title}`.toLowerCase();
        if (!allTokensIn(blob, tokens)) continue;
        const deep = deepDiveSlug(item.slug);
        hits.push({
          title: item.name,
          snippet: item.use || item.one || sub.title,
          href: `/repos/${deep ?? item.slug}`,
        });
        if (hits.length >= 8) return hits;
      }
    }
  }
  return hits;
}
