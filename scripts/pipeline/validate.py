#!/usr/bin/env python3
"""Validate an issue JSON against the local schema (no extra deps)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URI_RE = re.compile(r"^https?://")
KINDS = {"hot", "talk", "rt", "doc"}
KST = timezone(timedelta(hours=9))
VOICE_BAN = (
    "하십시오",
    "칸에 적",
    "칸을 나눠",
    "내부 메모에",
    "공식 발표문과 1차 매체 숫자를 맞춰 본 뒤에",
)


def err(path: str, msg: str, bag: list[str]) -> None:
    bag.append(f"{path}: {msg}")


def require(obj: dict, keys: list[str], path: str, bag: list[str]) -> None:
    for k in keys:
        if k not in obj:
            err(path, f"missing {k}", bag)


def check(issue: dict) -> list[str]:
    bag: list[str] = []
    require(
        issue,
        [
            "date",
            "title",
            "heroline",
            "dek",
            "tag",
            "briefMin",
            "readMin",
            "briefing",
            "keywords",
            "mainEvent",
            "keynums",
            "timeline",
            "intro",
            "analysis",
            "mood",
            "tips",
            "method",
        ],
        "$",
        bag,
    )
    if not DATE_RE.match(str(issue.get("date", ""))):
        err("date", "YYYY-MM-DD required", bag)
    if not (3 <= len(issue.get("briefing") or []) <= 14):
        err("briefing", "need 3–14 items", bag)
    if not (3 <= len(issue.get("keynums") or []) <= 16):
        err("keynums", "need 3–16 items", bag)
    if len(issue.get("timeline") or []) < 3:
        err("timeline", "need ≥3", bag)
    if not (2 <= len(issue.get("analysis") or []) <= 14):
        err("analysis", "need 2–14", bag)
    if len(issue.get("tips") or []) < 1:
        err("tips", "need ≥1", bag)
    mood = issue.get("mood")
    if not isinstance(mood, dict):
        err("mood", "must be an object with shift/grow/caution/heat", bag)
        mood = {}
    for k in ("shift", "grow", "caution", "heat"):
        if not mood.get(k):
            err("mood", f"missing {k}", bag)

    ids = []
    for i, b in enumerate(issue.get("briefing") or []):
        if not isinstance(b, dict):
            err(f"briefing[{i}]", "must be object", bag)
            continue
        require(b, ["id", "headline", "summary"], f"briefing[{i}]", bag)
        ids.append(b.get("id"))
    for i, a in enumerate(issue.get("analysis") or []):
        p = f"analysis[{i}]"
        if not isinstance(a, dict):
            err(p, "must be object", bag)
            continue
        require(a, ["id", "title", "bullets", "body", "takeaway", "tags", "sources"], p, bag)
        if len(a.get("bullets") or []) < 2:
            err(p + ".bullets", "need ≥2", bag)
        if len(a.get("body") or []) < 1:
            err(p + ".body", "need ≥1", bag)
        if len(a.get("sources") or []) < 1:
            err(p + ".sources", "need ≥1", bag)
        for j, s in enumerate(a.get("sources") or []):
            if not isinstance(s, dict):
                err(f"{p}.sources[{j}]", "must be object", bag)
                continue
            if s.get("kind") not in KINDS:
                err(f"{p}.sources[{j}].kind", "hot|talk|rt|doc", bag)
            url = str(s.get("url") or "")
            if not URI_RE.match(url):
                err(f"{p}.sources[{j}].url", "http(s) url", bag)
            if "example.com" in url:
                err(f"{p}.sources[{j}].url", "example.com 금지 — 수집 링크를 넣습니다", bag)
        take = a.get("takeaway") or ""
        if "하십시오" in take:
            err(p + ".takeaway", "시사점은 입니다/됩니다 톤. '하십시오' 금지", bag)
        for bad in VOICE_BAN:
            if bad in take or any(bad in (x or "") for x in (a.get("body") or [])):
                err(p, f"편집 메모 투 금지: {bad}", bag)
                break
        if len(take) < 60:
            err(p + ".takeaway", "시사점은 두 문장, 60자 이상", bag)
        if take.count("다.") + take.count("요.") < 1:
            err(p + ".takeaway", "종결 어미가 없습니다", bag)
        if a.get("id") not in ids:
            err(p + ".id", "should match a briefing id", bag)
        for para in a.get("body") or []:
            if isinstance(para, str) and len(para) < 80:
                err(p + ".body", "본문 한 단은 80자 이상", bag)
                break
    takes = [(a.get("takeaway") or "") for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    if takes and len(takes) != len(set(takes)):
        err("analysis.takeaway", "시사점 복붙 금지", bag)
    return bag


def normalize_headline(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"[\s\u200b-\u200f\u2028\u2029]+", "", s)
    return re.sub(r"[^\w가-힣]", "", s)


def url_core(u: str) -> str:
    try:
        p = urlparse(u.strip())
        host = (p.hostname or "").lower()
        path = (p.path or "").rstrip("/")
        return f"{host}{path}"
    except Exception:
        return u.strip().rstrip("/")


def check_quality(
    issue: dict,
    collected_urls: set[str] | None,
    prev: dict | None,
    date_str: str | None,
) -> tuple[list[str], list[str]]:
    """내용 품질 게이트. (errors, warnings) — warnings는 실패시키지 않는다."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. 발행일 일치 (수동 재실행·백필은 --date override)
    if date_str and issue.get("date") != date_str:
        errors.append(f"date: {issue.get('date')} != {date_str} (수동 재실행이면 --date로 지정)")

    # 2. 헤드라인 중복 (정규화 후 비교)
    heads: list[tuple[str, str]] = []
    for b in issue.get("briefing") or []:
        if isinstance(b, dict):
            heads.append(("briefing", normalize_headline(b.get("headline"))))
    for a in issue.get("analysis") or []:
        if isinstance(a, dict):
            heads.append(("analysis", normalize_headline(a.get("title"))))
    seen: dict[str, str] = {}
    for kind, h in heads:
        if not h:
            continue
        if h in seen:
            errors.append(f"headline-dup: {kind} 항목이 {seen[h]} 항목과 중복")
        else:
            seen[h] = kind

    # 3. 출력 URL ⊆ 수집 URL (환각 URL 방지)
    if collected_urls is not None:
        for i, a in enumerate(issue.get("analysis") or []):
            if not isinstance(a, dict):
                continue
            for s in a.get("sources") or []:
                u = str((s or {}).get("url") or "")
                if u and url_core(u) not in collected_urls:
                    errors.append(f"analysis[{i}].sources: 수집되지 않은 URL {u[:70]}")

    # 4. 전날 호 재탕 (warning — 이어지는 이슈도 있으므로)
    if prev:
        prev_heads: set[str] = set()
        for b in prev.get("briefing") or []:
            if isinstance(b, dict):
                prev_heads.add(normalize_headline(b.get("headline")))
        for a in prev.get("analysis") or []:
            if isinstance(a, dict):
                prev_heads.add(normalize_headline(a.get("title")))
        for kind, h in heads:
            if h and h in prev_heads:
                warnings.append(f"prev-dup: {kind} 헤드라인이 전날 호와 중복될 수 있음")
                break

    # 5. keynums 미검증 문구 잔류 (warning — 프론트에서 제외되지만 파이프라인도 경고)
    for k in issue.get("keynums") or []:
        sub = str((k or {}).get("sub") or "")
        if "교차검증 전" in sub or "초안" in sub:
            warnings.append("keynums: sub에 미검증 표시 잔류 (공개 지면에서는 제외됨)")
            break

    # 6. timeline t 포맷 (warning) — "MM/DD HH:MM" 권장, 구 형식 "MM-DD"도 허용
    for t in issue.get("timeline") or []:
        tt = str((t or {}).get("t") or "")
        if not tt:
            continue
        m = re.match(r"^(\d{2})[/-](\d{2})(?: (\d{2}):(\d{2}))?$", tt)
        ok = bool(m)
        if ok:
            mo, day = int(m.group(1)), int(m.group(2))
            ok = 1 <= mo <= 12 and 1 <= day <= 31
            if ok and m.group(3) is not None:
                ok = 0 <= int(m.group(3)) <= 23 and 0 <= int(m.group(4)) <= 59
        if not ok:
            warnings.append(f"timeline: t 포맷 비정상 '{tt}' (MM/DD HH:MM 기대)")
            break

    # 7. 목표 범위 초과 (warning)
    nb = len(issue.get("briefing") or [])
    if nb > 7:
        warnings.append(f"briefing: 목표 5~7 초과 ({nb}개)")
    for a in issue.get("analysis") or []:
        ex = str((a or {}).get("extra") or "")
        if len(ex) > 300:
            warnings.append(f"analysis extra: 300자 초과 ({len(ex)}자)")
            break

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--date", help="기대 발행일 (KST YYYY-MM-DD). 기본값: 오늘(KST)")
    ap.add_argument("--collected", type=Path, help="수집 스냅샷 JSON (URL ⊆ 검사)")
    ap.add_argument("--prev", type=Path, help="전날 호 JSON (재탕 검사)")
    args = ap.parse_args()
    date_str = args.date or datetime.now(KST).strftime("%Y-%m-%d")
    collected_urls: set[str] | None = None
    if args.collected and args.collected.exists():
        try:
            snap = json.loads(args.collected.read_text(encoding="utf-8"))
            collected_urls = {url_core(str(it.get("url") or "")) for it in snap.get("items", []) if it.get("url")}
        except Exception as e:
            print(f"WARN collected snapshot unreadable: {e}")
    prev: dict | None = None
    if args.prev and args.prev.exists():
        try:
            prev = json.loads(args.prev.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARN prev issue unreadable: {e}")
    failed = 0
    for f in args.files:
        issue = json.loads(f.read_text(encoding="utf-8"))
        bag = check(issue)
        qerr, qwarn = check_quality(issue, collected_urls, prev, date_str)
        bag.extend(qerr)
        if bag:
            failed += 1
            print(f"FAIL {f}")
            for line in bag:
                print("  -", line)
        else:
            nsrc = sum(len(a.get("sources") or []) for a in issue["analysis"])
            print(
                f"OK   {f.name} brief={len(issue['briefing'])} analysis={len(issue['analysis'])} "
                f"keynums={len(issue['keynums'])} tips={len(issue['tips'])} sources={nsrc}"
            )
        for line in qwarn:
            print(f"  ! WARN {f.name}: {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
