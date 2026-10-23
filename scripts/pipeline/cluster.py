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


def load(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
