const KEY = "fiv-subscribe-email";

export function getSubscribedEmail(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function subscribeEmail(email: string) {
  const existing = getSubscribedEmail();
  if (existing && existing.toLowerCase() === email.toLowerCase()) {
    return { ok: true as const, duplicate: true };
  }
  try {
    localStorage.setItem(KEY, email.trim());
    const listRaw = localStorage.getItem("fiv-subscribe-list");
    const list: string[] = listRaw ? (JSON.parse(listRaw) as string[]) : [];
    if (!list.some((e) => e.toLowerCase() === email.toLowerCase())) {
      list.push(email.trim());
      localStorage.setItem("fiv-subscribe-list", JSON.stringify(list));
    }
  } catch {
    /* ignore quota */
  }
  return { ok: true as const, duplicate: false };
}

export function unsubscribe() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
