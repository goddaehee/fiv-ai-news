import type { KeyNum } from "@/data/types";

/** 플레이스홀더로 쓰이는 val 값들. "0"은 유효한 수치이므로 제외하지 않는다. */
const PLACEHOLDER_VALS = new Set(["", "—", "–", "-", "N/A", "n/a", "?"]);

/** 파이프라인이 sub에 남기는 미검증 표시 문구. */
const DRAFT_RE = /초안|교차\s*검증\s*전|미검증/;

/**
 * 키 숫자를 공개 지면에 노출해도 되는지 판정한다.
 * - 검증 전(초안 · 교차검증 전) 수치는 노출하지 않는다
 * - 플레이스홀더(val이 "—" 등)도 노출하지 않는다
 * JSON은 런타임에 타입 검사를 받지 않으므로 옵셔널 체이닝으로 방어한다.
 */
export function isPublicKeyNum(k: KeyNum | undefined | null): boolean {
  if (!k) return false;
  const val = k.val?.trim() ?? "";
  const lab = k.lab?.trim() ?? "";
  if (!val || !lab) return false;
  if (PLACEHOLDER_VALS.has(val)) return false;
  if (DRAFT_RE.test(k.sub ?? "")) return false;
  return true;
}
