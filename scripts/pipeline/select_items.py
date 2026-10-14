#!/usr/bin/env python3
"""1주차: 선별 점수제 + 소스 쿼터 (품질 개선 계획 v5).

선별 점수제: 영향도·새로움·관련성·근거 각 0~2점 = 총 8점, 5점 미만 탈락.
소스 쿼터: 단일 출처 ≤25% (분모 = 당일 기사 수).
메인 기사 상한: 3~5개, 나머지는 단신 목록.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

MAX_MAIN = 5
MIN_MAIN = 3
SCORE_CUTOFF = 5
SOURCE_QUOTA = 0.25


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def score_bucket(items: list[dict], now: datetime | None = None) -> dict:
    """버킷(같은 주제 기사 묶음)을 4개 축으로 채점. 반환: {impact, novelty, relevance, evidence, total}."""
    now = now or datetime.now(timezone.utc)

    # 영향도: 몇 개 매체가 다뤘는지
    sources = {str(it.get("source") or "") for it in items}
    impact = 0 if len(sources) <= 1 else (1 if len(sources) == 2 else 2)

    # 새로움: 가장 최근 기사 기준
    newest = None
    for it in items:
        dt = _parse_date(str(it.get("published") or ""))
        if dt and (newest is None or dt > newest):
            newest = dt
    if newest:
        hours = (now - newest).total_seconds() / 3600
        novelty = 2 if hours <= 24 else (1 if hours <= 48 else 0)
    else:
        novelty = 1  # 날짜 불명 — 중간값

    # 관련성: 구체적 수치·고유명사 포함 여부
    blob = " ".join(f"{it.get('title','')} {it.get('summary','')}" for it in items)
    has_number = bool(re.search(r"\d+(\.\d+)?\s*(%|배|달러|억|만|점|분|시간|일)", blob))
    has_proper = bool(re.search(r"[A-Z][a-z]+ [A-Z]|GPT|Claude|Gemini|Anthropic|OpenAI|NVIDIA", blob))
    relevance = (1 if has_number else 0) + (1 if has_proper else 0)

    # 근거: 공식 출처 URL 포함 여부
    urls = [str(it.get("url") or "") for it in items]
    has_official = any("openai.com" in u or "anthropic.com" in u or "deepmind" in u
                       or "googleblog" in u or "nvidia.com" in u or "about.fb.com" in u
                       for u in urls)
    has_url = any(u.startswith("http") and "example.com" not in u for u in urls)
    evidence = 2 if has_official else (1 if has_url else 0)

    return {"impact": impact, "novelty": novelty, "relevance": relevance,
            "evidence": evidence, "total": impact + novelty + relevance + evidence}


def select_buckets(
    ranked: list[tuple[str, list[dict]]],
) -> tuple[list[tuple[str, list[dict], dict]], list[tuple[str, list[dict], dict]]]:
    """선별 점수제 + 쿼터 적용. 반환: (메인 기사, 단신 목록)."""
    scored = []
    for name, items in ranked:
        s = score_bucket(items)
        if s["total"] >= SCORE_CUTOFF:
            scored.append((name, items, s))
    # 점수 순 정렬 (동점 시 버킷 크기 순)
    scored.sort(key=lambda x: (-x[2]["total"], -len(x[1]), x[0]))

    # 메인 상한 + 소스 쿼터
    # 메인 기사가 3~5개면, 같은 출처 2개 = 40% > 25%이므로
    # 사실상 메인 기사는 출처당 1개까지만 허용한다.
    main: list[tuple[str, list[dict], dict]] = []
    rest: list[tuple[str, list[dict], dict]] = []
    used_sources: set[str] = set()
    for name, items, s in scored:
        if len(main) >= MAX_MAIN:
            rest.append((name, items, s))
            continue
        top_source = str(items[0].get("source") or "")
        if top_source in used_sources:
            rest.append((name, items, s))
            continue
        main.append((name, items, s))
        used_sources.add(top_source)

    return main, rest


def quota_report(selected: list[tuple[str, list[dict], dict]], total_articles: int | None = None) -> dict:
    """소스 쿼터 준수 여부 보고. 분모 = 당일 전체 기사 수 (메인 + 단신)."""
    counts: Counter = Counter()
    for _, items, _ in selected:
        counts[str(items[0].get("source") or "")] += 1
    total = total_articles if total_articles is not None else sum(counts.values())
    return {
        "total": total,
        "sources": dict(counts),
        "max_share": max(counts.values()) / total if total else 0,
        "quota_ok": (max(counts.values()) / total <= SOURCE_QUOTA) if total else True,
    }
