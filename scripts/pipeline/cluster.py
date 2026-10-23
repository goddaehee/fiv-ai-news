#!/usr/bin/env python3
"""Group collected items into editorial topic buckets."""

from __future__ import annotations

import json
import re
from collections import defaultdict

RULES: list[tuple[str, re.Pattern[str]]] = [
    # P16: 보안 사건은 제목에 회사명이 섞여도(예: "PHP Armageddon: OpenAI, Wiz…")
    # 회사 버킷으로 묻히지 않게 최상단에서 먼저 잡는다. php2shell이 openai
    # 버킷 16번째로 절단돼 톱뉴스가 누락된 실측(2026-10-23)의 재발 방지.
    ("security", re.compile(r"zero[- ]?day|vulnerabilit|exploit|malware|ransomware|data breach|breach(ed|ing)?\s+(of|at|into|it|the)\b|\bcve-\d|php2shell|remote code execution|critical flaw|hackers?\s+(spied|breach|stole|target|gained)", re.I)),
    ("gemini-voice", re.compile(r"gemini\s*3\.8|live extended|speech to speech|search live", re.I)),
    ("openai", re.compile(r"\bopenai\b|gpt-live|gpt-6|chatgpt|sora|codex|misalignment|astra for law", re.I)),
    ("anthropic", re.compile(r"anthropic|\bclaude\b|fable|amodei", re.I)),
    ("safety", re.compile(r"safety|cheatbench|reward hack|pace the frontier|kill switch|regulation|cheating", re.I)),
    ("law", re.compile(r"\blaw\b|legal search|courtlistener|lexis", re.I)),
    ("routing", re.compile(r"openrouter|wallet share|token share", re.I)),
    ("china", re.compile(r"\bz\.ai\b|zhipu|glm-5|chinese accelerator", re.I)),
    ("science", re.compile(r"science|x-ray|periodic neon|atlas|scientist", re.I)),
    ("chips", re.compile(r"\bgpu\b|h200|blackwell|mtia|inferenc|nvidia|tpu", re.I)),
    ("benchmark", re.compile(r"benchmark|leaderboard|artificial analysis|index|eval", re.I)),
    ("agents", re.compile(r"\bagent\b|mcp|harness|coding agent|computer use", re.I)),
    ("policy", re.compile(r"white house|sacks|washington|congress|export", re.I)),
    ("mna", re.compile(r"acqui|buys |bought |merger|deal worth", re.I)),
]


def blob(item: dict) -> str:
    return f"{item.get('title','')} {item.get('summary','')}"


def cluster(items: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        text = blob(it)
        hit = False
        for name, rx in RULES:
            if rx.search(text):
                buckets[name].append(it)
                hit = True
                break
        if not hit:
            buckets["other"].append(it)
    return {k: v for k, v in buckets.items() if v}


def rank_buckets(buckets: dict[str, list[dict]]) -> list[tuple[str, list[dict]]]:
    return sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))


# ---------------------------------------------------------------------------
# P16: 스토리 그룹 (교차보도 신호)
# 버킷은 주제 단위라 "같은 이야기를 몇 개 매체가 다뤘는가"를 잴 수 없었다.
# Claude Duet는 수집 10건인데도 anthropic 버킷 안에서 IPO에 밀려 탈락했다
# (2026-10-23 실측). 제목 토큰 유사도로 같은 이야기를 묶어 교차보도
# 매체 수를 신호로 만든다. 그룹핑은 근사치로 충분하다 — 목적은 선별·
# 페이로드 정렬의 우선순위 신호이지 분류의 정확성이 아니다.
# ---------------------------------------------------------------------------

_STORY_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "for", "on", "with", "and", "or",
    "as", "at", "by", "is", "are", "its", "it", "says", "say", "how", "why",
    "what", "will", "can", "from", "after", "over", "into", "about", "new",
    "ai",  # 거의 모든 제목에 있어 변별력이 없다
}

_STORY_SIM_THRESHOLD = 0.28


def _story_tokens(title: str) -> set[str]:
    """제목 비교용 토큰. GNews 제목 끝의 ' - 매체명' 접미사는 매체마다
    달라 유사도를 깎으므로, 꼬리가 짧으면(≤5 토큰) 잘라내고 비교한다."""
    t = title or ""
    head, sep, _tail = t.rpartition(" - ")
    if sep and len(_story_raw_tokens(head)) >= 3 and len(_story_raw_tokens(_tail)) <= 5:
        t = head
    return _story_raw_tokens(t)


def _story_raw_tokens(title: str) -> set[str]:
    s = re.split(r"[^0-9a-zA-Z]+", (title or "").lower())
    return {p for p in s if len(p) >= 3 and p not in _STORY_STOPWORDS}


def _story_sim(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _outlet_key(it: dict) -> str:
    """교차보도 판정용 매체 키. GNews 아이템은 source 라벨이 전부 같아서
    origin_url(실발행처 홈페이지)의 도메인으로 구분해야 실제 매체 수가 나온다.
    (2026-10-23 Duet 실측: 라벨 기준 2개 매체로 과소 계산, 실제로는 10개 매체)"""
    origin = str(it.get("origin_url") or "")
    if origin:
        from urllib.parse import urlparse
        host = (urlparse(origin).hostname or "").lower()
        if host:
            return host.removeprefix("www.")
    return str(it.get("source") or "")


def story_groups(items: list[dict]) -> list[dict]:
    """같은 이야기끼리 탐욕 그룹핑. 반환: [{items, sources(set), coverage}].

    coverage = 그 이야기를 다룬 서로 다른 매체 수(_outlet_key 기준).
    1이면 단독 보도. 대표 아이템은 그룹의 첫 아이템(수집 순서상 먼저인 것)."""
    groups: list[dict] = []
    for it in items:
        toks = _story_tokens(str(it.get("title") or ""))
        best = None
        best_sim = 0.0
        for g in groups:
            sim = _story_sim(toks, g["tokens"])
            if sim >= _STORY_SIM_THRESHOLD and sim > best_sim:
                best, best_sim = g, sim
        if best is None:
            groups.append({
                "items": [it],
                "sources": {_outlet_key(it)},
                "tokens": toks,
            })
        else:
            # 대표(첫 아이템) 토큰과만 비교한다 — 그룹 토큰을 계속 합치면
            # 느슨한 연결로 서로 다른 이야기까지 연쇄 병합되는 드리프트가 생긴다.
            best["items"].append(it)
            best["sources"].add(_outlet_key(it))
    for g in groups:
        g["coverage"] = len(g["sources"])
    return groups


def item_coverage(items: list[dict]) -> dict[int, int]:
    """아이템 id() → 그 아이템이 속한 스토리 그룹의 coverage 맵."""
    out: dict[int, int] = {}
    for g in story_groups(items):
        for it in g["items"]:
            out[id(it)] = g["coverage"]
    return out


# ---------------------------------------------------------------------------
# P17: 톱뉴스 강제 편입 (must-cover)
# P16의 coverage 신호는 페이로드 정렬까지만 바꿨고 최종 선택은 여전히 LLM
# 재량이라 php2shell(CVSS 9.2)이 또 탈락했다 (2026-10-23 3차 평가).
# "반드시 analysis로 다뤄야 할 이야기"를 결정적으로 계산해 draft 페이로드와
# validate 게이트가 같은 함수를 공유한다 (판정 기준이 어긋나면 재시도가
# 수렴하지 않는다는 P1 교훈).
#
# 신호 2종 (개별 story_group 단위로 판정):
# - coverage: topic 버킷('other' 제외)에서 교차보도 coverage ≥ 4.
#   'other'는 잡다한 지역 매체 템플릿 공지(예: 지역지 AI 정책 고지 cov=5)가
#   섞이는 버킷이라 제외한다 (2026-10-23 스냅샷 실측).
# - security: security 버킷에서 같은 사건 아이템 ≥2개 + 제목에 critical
#   마커(zero-day·CVE·CVSS·emergency patch 등). php2shell은 그룹 coverage가
#   2까지밖에 안 올라가므로 coverage 신호만으로는 못 잡는다.
#
# 같은 이야기가 여러 그룹으로 쪼개지는 문제(Duet 6+5, php2shell 2+1+1+1)는
# 그룹 병합이 아니라 **신호를 통과한 후보끼리의 중복 제거**로 다룬다.
# 전체 그룹 병합은 두 번 시도해 두 번 다 무관한 이야기까지 연쇄 흡수돼
# coverage가 14~21로 팽창했다 (흔한 토큰 매개 + Title Case 헤드라인 때문에
# 대문자 휴리스틱도 무력). 후보는 이미 임계값을 넘은 소수라, 서명 토큰을
# 공유하는 후보끼리만 합치고 URL 집합을 넓히는 쪽이 안전하다.
# 서명 토큰: 그 후보 아이템 제목들에만 등장하는 토큰 (df ≤ 후보 아이템
# 수 + 2, 4자 이상). 'duet'(df 12, 후보 11건)·'php2shell'(df 5, 후보 3건)이
# 해당하고 'claude'·'chatgpt' 같은 범용 토큰은 df가 커서 탈락한다.
# 게이트용 URL 집합은 서명 토큰을 제목에 포함한 스냅샷 전체 아이템으로
# 확장한다 — 그룹이 쪼개져 있어도 LLM이 그 이야기 아이템 중 하나만 인용하면
# 편입으로 인정한다.
# ---------------------------------------------------------------------------

_CRITICAL_RE = re.compile(
    r"zero[- ]?day|cve-\d|cvss|emergency patch|actively exploited"
    r"|remote code execution|\brce\b|critical (flaw|vulnerabilit|patch)"
    r"|malware|backdoor|supply[- ]chain|ransomware",
    re.I,
)
MUST_COVERAGE = 4
MUST_MAX_STORIES = 4


# 서명 토큰에서 제외할 일반어. 이야기 이름(제품명·사건명)은 살아남고
# 서술어·일반 명사('work', 'race', 'critical' 등)는 걸러진다.
_SIG_STOPLIST = {
    "work", "works", "working", "race", "life", "great", "this", "that",
    "will", "says", "news", "first", "more", "than", "then", "over",
    "under", "after", "before", "about", "into", "their", "there",
    "these", "those", "being", "using", "used", "make", "makes", "made",
    "take", "takes", "just", "like", "even", "also", "back", "well",
    "much", "many", "most", "other", "another", "every", "with", "from",
    "critical", "emergency", "patch", "patches", "vulnerability",
    "vulnerabilities", "flaw", "flaws", "attack", "attacks", "breach",
    "security", "exploited", "exploit", "hack", "hacked", "hackers",
    "malware", "warning", "warns", "alert", "update", "updates",
    "report", "reports",
}


def _signature_tokens(titles_tokens: list[set[str]], df: dict[str, int],
                      total_items: int) -> set[str]:
    """이야기 서명 토큰 (중복 제거용): 후보 아이템 중 2개 이상의 제목에
    등장하고, 그날 스냅샷 전체에서도 흔하지 않은 토큰.
    'duet'(후보 2그룹 모두 등장, df 12)·'php2shell'(df 5)이 해당하고
    'claude'(df 수십)·'chatgpt'(범용) 같은 토큰은 df 상한에서 탈락한다."""
    from collections import Counter
    cnt: Counter = Counter()
    for toks in titles_tokens:
        for t in toks:
            cnt[t] += 1
    cap = max(6, int(0.06 * total_items))
    return {t for t, n in cnt.items()
            if n >= 2 and len(t) >= 4 and t not in _SIG_STOPLIST
            and df.get(t, 0) <= cap}


def must_cover_stories(items: list[dict], min_coverage: int = MUST_COVERAGE,
                       max_stories: int = MUST_MAX_STORIES) -> list[dict]:
    """반드시 analysis로 다뤄야 할 당일 톱뉴스 목록.

    반환: [{title, coverage, n, bucket, signal, urls}] — urls는 그 이야기
    아이템들의 url(원본 문자열) 집합. 게이트는 analysis의 sources URL과
    대조한다. draft와 validate가 같은 입력(수집 스냅샷 items)에 대해 같은
    결과를 내는 것이 전제다."""
    if not items:
        return []
    buckets = cluster(items)
    bucket_of: dict[int, str] = {}
    for name, its in buckets.items():
        for it in its:
            bucket_of[id(it)] = name

    df: dict[str, int] = {}
    item_tokens: dict[int, set[str]] = {}
    for it in items:
        toks = _story_tokens(str(it.get("title") or ""))
        item_tokens[id(it)] = toks
        for t in toks:
            df[t] = df.get(t, 0) + 1

    # 1) 신호 판정 (그룹 단위)
    cands: list[dict] = []
    for g in story_groups(items):
        bucket = bucket_of.get(id(g["items"][0]), "other")
        signal = None
        if bucket != "other" and g["coverage"] >= min_coverage:
            signal = "coverage"
        elif (bucket == "security" and len(g["items"]) >= 2
              and any(_CRITICAL_RE.search(str(it.get("title") or ""))
                      for it in g["items"])):
            signal = "security"
        if signal:
            cands.append({
                "items": list(g["items"]),
                "sources": set(g["sources"]),
                "bucket": bucket,
                "signal": signal,
                "rep": g["items"][0],
            })

    # 2) 같은 이야기 후보 중복 제거 (서명 토큰 공유 시 합집합)
    for c in cands:
        c["sig"] = _signature_tokens(
            [item_tokens[id(it)] for it in c["items"]], df, len(items))
    cands.sort(key=lambda c: (-len(c["sources"]), -len(c["items"])))
    merged: list[dict] = []
    for c in cands:
        host = None
        for m in merged:
            if m["sig"] & c["sig"]:
                host = m
                break
        if host is None:
            merged.append(c)
        else:
            host["items"].extend(c["items"])
            host["sources"] |= c["sources"]
            host["sig"] |= c["sig"]
            if c["signal"] == "coverage":
                host["signal"] = "coverage"

    # 3) 게이트용 URL 확장: 서명 토큰 중에서도 그 이야기 규모로만 등장하는
    # 토큰(df ≤ 병합 아이템 수 + 2)을 제목에 포함한 아이템 전체.
    # 'duet'(df 12, 병합 11건)은 통과하고 'critical'(여러 보안 사건 공유)처럼
    # 후보보다 넓게 퍼진 토큰은 확장 근거에서 빠진다.
    for m in merged:
        urls = {str(it.get("url") or "") for it in m["items"] if it.get("url")}
        xsig = {t for t in m["sig"] if df.get(t, 0) <= len(m["items"]) + 2}
        if xsig:
            for it in items:
                if it.get("url") and item_tokens[id(it)] & xsig:
                    urls.add(str(it["url"]))
        m["urls"] = urls
        m["coverage"] = len(m["sources"])

    # 4) 신호별 교대 선택: coverage 후보만으로 cap을 채우면 치명적 보안
    # 사건이 밀려난다. 번갈아 뽑아 어느 쪽도 cap에 굶지 않게 한다.
    cov_c = sorted((m for m in merged if m["signal"] == "coverage"),
                   key=lambda m: (-m["coverage"], -len(m["items"])))
    sec_c = sorted((m for m in merged if m["signal"] == "security"),
                   key=lambda m: (-len(m["items"]), -m["coverage"]))
    chosen: list[dict] = []
    while len(chosen) < max_stories and (cov_c or sec_c):
        if cov_c:
            chosen.append(cov_c.pop(0))
        if len(chosen) < max_stories and sec_c:
            chosen.append(sec_c.pop(0))
    return [{
        "title": str(m["rep"].get("title") or ""),
        "coverage": m["coverage"],
        "n": len(m["items"]),
        "bucket": m["bucket"],
        "signal": m["signal"],
        "urls": m["urls"],
    } for m in chosen]


def load(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
