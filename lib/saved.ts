const KEY = "fiv-saved-repos";
const READ_KEY = "fiv-last-read";
const INT_KEY = "fiv-repo-interest";

function readList(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function writeList(slugs: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(slugs));
  } catch {
    /* ignore */
  }
}

export function listSavedRepos() {
  return readList();
}

export function isRepoSaved(slug: string) {
  return readList().includes(slug);
}

export function toggleSavedRepo(slug: string) {
  const list = readList();
  const next = list.includes(slug) ? list.filter((s) => s !== slug) : [slug, ...list];
  writeList(next);
  return next.includes(slug);
}

export function markRead(date: string) {
  try {
    localStorage.setItem(READ_KEY, date);
  } catch {
    /* ignore */
  }
}

export function getLastRead() {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(READ_KEY);
  } catch {
    return null;
  }
}

export function readInterestMap(): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(INT_KEY);
    return raw ? (JSON.parse(raw) as Record<string, number>) : {};
  } catch {
    return {};
  }
}

export function getInterest(slug: string) {
  return readInterestMap()[slug] ?? 0;
}

export function setInterest(slug: string, level: number) {
  const map = readInterestMap();
  const next = map[slug] === level ? 0 : level;
  if (next) map[slug] = next;
  else delete map[slug];
  try {
    localStorage.setItem(INT_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
  return next;
}
