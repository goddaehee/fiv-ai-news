const KEY = "fiv-saved-repos";
const READ_KEY = "fiv-last-read";

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
