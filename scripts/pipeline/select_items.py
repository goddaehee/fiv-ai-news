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


def bucket_domain(items: list[dict]) -> str:
    """버킷 대표 아이템(items[0])의 URL에서 비교용 도메인 추출.
    validate.extract_domain과 동일 규격: 소문자, www. 제거. 실패 시 빈 문자열.
    P5: origin_url(Google News <source url>)이 있으면 그것을 우선 사용."""
    if not items:
        return ""
    from urllib.parse import urlparse
    try:
        url = items[0].get("origin_url") or items[0].get("url") or ""
        host = (urlparse(str(url)).hostname or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _host(url: str) -> str:
    """URL에서 호스트 추출 (서브도메인 오탐 방지)."""
    from urllib.parse import urlparse
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


OFFICIAL_HOSTS = {
    "openai.com", "anthropic.com", "deepmind.google",
    "blog.google", "googleblog.com", "blogs.nvidia.com", "nvidia.com",
    "about.fb.com", "engineering.fb.com",
}
OFFICIAL_PREFIXES = ("huggingface.co/blog/",)  # HF는 /blog 경로만 1차 출처


def _is_official(url: str) -> bool:
    """1차 출처 판정: 호스트 단위 정확 일치 (substring 비교 아님).
    서브도메인 허용: host == 공식도메인 또는 host가 '.' + 공식도메인으로 끝남.
    예: www.openai.com → OK, blog.google.evil.com → NG.
    """
    host = _host(url).lower()
    for dom in OFFICIAL_HOSTS:
        if host == dom or host.endswith("." + dom):
            return True
    # HF: /blog 경로만 1차 출처. /blogger, /blog-spam은 제외.
    if host == "huggingface.co":
        from urllib.parse import urlparse
        path = urlparse(url).path
        if path == "/blog" or path.startswith("/blog/"):
            return True
    return False


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    # P7: ISO 8601 전체 파싱 (타임존 오프셋 포함, 초 없는 형식도 처리)
    # collect.py는 "2026-10-16T10:30+09:00" 형식으로 저장 (초 없음, KST 오프셋)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    # 폴백: 기존 형식들
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
    # 1차 출처 = 발표 주체 본인의 공식 채널 (2차 매체인 TechCrunch/Verge/Ars는 제외)
    # 호스트 단위 판정 (_is_official) — substring 비교 아님
    has_official = any(_is_official(u) for u in urls)
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
    used_domains: set[str] = set()  # P4: 도메인 기준 중복 제거 (피드 라벨 필터와 병행)
    for name, items, s in scored:
        if len(main) >= MAX_MAIN:
            rest.append((name, items, s))
            continue
        top_source = str(items[0].get("source") or "")
        if top_source in used_sources:
            rest.append((name, items, s))
            continue
        dom = bucket_domain(items)
        if dom and dom in used_domains:
            rest.append((name, items, s))
            continue
        main.append((name, items, s))
        used_sources.add(top_source)
        if dom:
            used_domains.add(dom)

    # P4 fallback: MIN_MAIN 미달 시 도메인 규칙만 완화 (피드 라벨 필터는 유지)
    if len(main) < MIN_MAIN:
        for name, items, s in scored:
            if len(main) >= MIN_MAIN:
                break
            if any(name == m[0] for m in main):
                continue
            top_source = str(items[0].get("source") or "")
            if top_source in used_sources:
                continue
            main.append((name, items, s))
            used_sources.add(top_source)
        main_names = {m[0] for m in main}
        rest = [t for t in rest if t[0] not in main_names]

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
