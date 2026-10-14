#!/usr/bin/env python3
"""1주차: 선별 점수제 + 소스 쿼터 테스트."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "pipeline"))
from select_items import score_bucket, select_buckets, quota_report

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def item(title, source, url, published=NOW, summary=""):
    return {"title": title, "source": source, "url": url, "published": published, "summary": summary, "kind": "doc"}


def test_score_high():
    s = score_bucket([item("OpenAI GPT-6 release 50% faster", "OpenAI News", "https://openai.com/x", summary="New model")])
    assert s["total"] >= 5, s
    print("ok: high score")


def test_score_low():
    s = score_bucket([item("Random thing", "HN AI", "https://example.com/x", published="2026-10-01T00:00:00")])
    assert s["total"] < 5, s
    print("ok: low score dropped")


def test_quota_one_per_source():
    ranked = [
        ("openai", [item("OpenAI A 50% faster", "OpenAI News", "https://openai.com/a")]),
        ("openai2", [item("OpenAI B safety 90%", "OpenAI News", "https://openai.com/b")]),
        ("anthropic", [item("Anthropic Claude 200 dollar", "Anthropic News", "https://anthropic.com/a")]),
        ("chips", [item("NVIDIA H200 95 points", "NVIDIA Blog", "https://blogs.nvidia.com/a")]),
    ]
    main, rest = select_buckets(ranked)
    sources = [it[0]["source"] for _, it, _ in main]
    assert len(sources) == len(set(sources)), f"duplicate source in main: {sources}"
    print("ok: quota one per source")


def test_quota_report():
    q = quota_report([("a", [item("x", "OpenAI News", "https://openai.com/a")], {})], total_articles=8)
    assert q["max_share"] == 0.125 and q["quota_ok"]
    print("ok: quota report")


if __name__ == "__main__":
    test_score_high()
    test_score_low()
    test_quota_one_per_source()
    test_quota_report()
    print("1주차 tests passed")
