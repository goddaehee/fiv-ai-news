const JOSA = ["에서", "으로", "은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도"];

export function normalizeTerm(value: string) {
  return value.toLowerCase().normalize("NFC").trim().replace(/\s+/g, " ");
}

export function tokenize(q: string) {
  return normalizeTerm(q).split(/\s+/).filter(Boolean);
}

function variants(tok: string) {
  const out = [tok];
  for (const j of JOSA) {
    if (!tok.endsWith(j)) continue;
    const stem = tok.slice(0, -j.length);
    if ([...stem].length >= 2) out.push(stem);
    break;
  }
  return out;
}

export function hayHas(hay: string, tok: string) {
  if (hay.includes(tok)) return true;
  return variants(tok).slice(1).some((v) => v && hay.includes(v));
}

export function allTokensIn(hay: string, tokens: string[]) {
  return tokens.every((t) => hayHas(hay, t));
}

export function highlightTerms(text: string, tokens: string[]): { t: string; hit: boolean }[] {
  if (!tokens.length) return [{ t: text, hit: false }];
  const parts: { t: string; hit: boolean }[] = [{ t: text, hit: false }];
  for (const tok of tokens) {
    const next: { t: string; hit: boolean }[] = [];
    for (const part of parts) {
      if (part.hit) {
        next.push(part);
        continue;
      }
      const src = part.t;
      const low = src.toLowerCase();
      let found = false;
      for (const v of variants(tok)) {
        const at = low.indexOf(v);
        if (at === -1) continue;
        found = true;
        if (at > 0) next.push({ t: src.slice(0, at), hit: false });
        next.push({ t: src.slice(at, at + v.length), hit: true });
        next.push({ t: src.slice(at + v.length), hit: false });
        break;
      }
      if (!found) next.push(part);
    }
    parts.length = 0;
    parts.push(...next);
  }
  return parts;
}
