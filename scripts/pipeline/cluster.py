#!/usr/bin/env python3
"""Group collected items into editorial topic buckets."""

from __future__ import annotations

import json
import re
from collections import defaultdict

RULES: list[tuple[str, re.Pattern[str]]] = [
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


def load(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
