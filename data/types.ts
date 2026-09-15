export type SourceKind = "hot" | "talk" | "rt" | "doc";

export type Source = {
  handle: string;
  url: string;
  kind: SourceKind;
};

export type BriefItem = {
  id: string;
  headline: string;
  summary: string;
};

export type KeyNum = {
  val: string;
  lab: string;
  sub: string;
};

export type TimelineItem = {
  t: string;
  d: string;
};

export type Analysis = {
  id: string;
  title: string;
  bullets: string[];
  body: string[];
  extra?: string;
  takeaway: string;
  tags: string[];
  sources: Source[];
};

export type Tip = {
  title: string;
  body: string;
  via: string;
};

export type Mood = {
  shift: string;
  grow: string;
  caution: string;
  heat: string;
};

export type Issue = {
  date: string;
  title: string;
  heroline: string;
  dek: string;
  tag: string;
  briefMin: number;
  readMin: number;
  briefing: BriefItem[];
  keywords: string[];
  mainEvent: string;
  keynums: KeyNum[];
  timeline: TimelineItem[];
  intro: string;
  analysis: Analysis[];
  mood: Mood;
  tips: Tip[];
  method: string;
};

export type RepoCategory =
  | "agents"
  | "skills"
  | "cli"
  | "local"
  | "mcp"
  | "web";

export type Repo = {
  slug: string;
  name: string;
  repo: string;
  category: RepoCategory;
  subcategory: string;
  stars: string;
  license: string;
  lang: string;
  updated: string;
  trendRank: number;
  oneLiner: string;
  analogyTitle: string;
  analogy: string;
  why: string;
  pain: string;
  fix: string;
  compare: { vs: string; point: string }[];
  stack: { name: string; role: string; detail: string }[];
  languages: { name: string; pct: string; bar: number; note: string }[];
  architecture: string;
  patterns: { name: string; body: string }[];
  tree: string;
  learn: { title: string; body: string }[];
  requirements: { item: string; min: string; rec: string }[];
  exercises: { title: string; body: string }[];
  keywords: { word: string; meaning: string }[];
  links: { label: string; href: string }[];
};

export type Faq = { q: string; a: string };
