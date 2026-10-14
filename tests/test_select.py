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


def test_evidence_primary_vs_secondary():
    # 1차 출처: 발표 주체 본인 채널 → evidence 2
    s = score_bucket([item("OpenAI GPT-6 50% faster", "OpenAI News", "https://openai.com/a")])
    assert s["evidence"] == 2, s
    s = score_bucket([item("HF 70B model release", "Hugging Face", "https://huggingface.co/blog/a")])
    assert s["evidence"] == 2, s
    # Google Blog 회귀: blog.google은 1차 출처
    s = score_bucket([item("Gemini voice 40 languages", "Google Blog", "https://blog.google/a")])
    assert s["evidence"] == 2, s
    # 2차 출처: 보도 매체 → evidence 1 (TechCrunch는 1차 아님)
    s = score_bucket([item("AI startup 100M funding", "TechCrunch AI", "https://techcrunch.com/a")])
    assert s["evidence"] == 1, s
    # HF 일반 페이지도 1차 아님
    s = score_bucket([item("HF 70B model release", "Hugging Face", "https://huggingface.co/a")])
    assert s["evidence"] == 1, s
    # 유사 도메인 오탐 방지: blog.google.evil.com은 1차 아님
    s = score_bucket([item("Fake Google blog", "Fake", "https://blog.google.evil.com/a")])
    assert s["evidence"] == 1, s
    s = score_bucket([item("Fake", "Fake", "https://google.com.evil.io/a")])
    assert s["evidence"] == 1, s
    s = score_bucket([item("Fake", "Fake", "https://evilblog.google/a")])
    assert s["evidence"] == 1, s
    # HF /blogger 경로는 1차 아님
    s = score_bucket([item("HF blogger", "HF", "https://huggingface.co/blogger/a")])
    assert s["evidence"] == 1, s
    # 서브도메인 허용: www.openai.com은 1차 출처
    s = score_bucket([item("OpenAI news", "OpenAI", "https://www.openai.com/news/a")])
    assert s["evidence"] == 2, s
    print("ok: evidence primary vs secondary")


if __name__ == "__main__":
    test_score_high()
    test_score_low()
    test_quota_one_per_source()
    test_quota_report()
    test_evidence_primary_vs_secondary()
    print("1주차 tests passed")
