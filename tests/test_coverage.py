#!/usr/bin/env python3
"""coverage.py + skeleton 경계 테스트 (구현 교차 평가 반영)."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "pipeline"))
from coverage import coverage
from draft import skeleton

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def item(title, source, url, published=NOW, summary=""):
    return {"title": title, "source": source, "url": url, "published": published, "summary": summary, "kind": "doc"}


def test_coverage_partial():
    clone = {"briefing": [{"headline": "Google Gemini 4 Argon 공개", "summary": "구글이 새 모델 공개"}]}
    r = coverage(clone, ["Google Gemini 4 Argon 공개", "Anthropic 증류 방어", "OpenAI 새 모델"])
    assert 0 < r["rate"] < 1.0, r
    print("ok: coverage partial")


def test_coverage_full():
    clone = {"briefing": [{"headline": "Google Gemini 4 Argon 공개", "summary": "구글이 새 모델 공개"}]}
    r = coverage(clone, ["Google Gemini 4 Argon 공개"])
    assert r["rate"] == 1.0, r
    print("ok: coverage full")


def test_coverage_miss():
    clone = {"briefing": [{"headline": "Higgsfield 영상", "summary": "영상 도구"}]}
    r = coverage(clone, ["Google Gemini 4 Argon 공개", "Anthropic 증류 방어"])
    assert r["rate"] == 0.0 and len(r["missed"]) == 2, r
    print("ok: coverage miss")


def test_skeleton_main_boundary():
    # 7개 버킷 → 메인 ≤5개
    items = []
    for i, (src, kw, url) in enumerate([
        ("OpenAI News", "OpenAI GPT-6 50% faster", "https://openai.com/news/a"),
        ("Anthropic News", "Anthropic Claude 200 dollar", "https://anthropic.com/news/a"),
        ("Google Blog", "Google Gemini 3.8 voice 40 languages", "https://blog.google/a"),
        ("NVIDIA Blog", "NVIDIA H200 95 points", "https://blogs.nvidia.com/a"),
        ("Meta News", "Meta safety policy 90% detection", "https://about.fb.com/a"),
        ("Hugging Face", "Hugging Face 70B model release", "https://huggingface.co/blog/a"),
        ("TechCrunch AI", "TechCrunch AI startup 100 million funding", "https://techcrunch.com/a"),
    ]):
        items.append(item(kw, src, url))
    snap = {"date": "2026-10-14", "count": len(items), "items": items}
    skel = skeleton(snap)
    assert len(skel["analysis"]) <= 5, f"analysis {len(skel['analysis'])} > 5"
    assert len(skel["briefing"]) >= len(skel["analysis"])
    print(f"ok: skeleton boundary (briefing={len(skel['briefing'])}, analysis={len(skel['analysis'])})")


def test_title_join_regression():
    # title join 버그 회귀: 헤드라인에 여러 단어가 있어도 join이 실패하지 않음
    items = [
        item("OpenAI GPT-6 release 50% faster inference speed", "OpenAI News", "https://openai.com/a"),
        item("Anthropic Claude new feature 200 dollar plan", "Anthropic News", "https://anthropic.com/a"),
        item("Google Gemini voice update 40 languages support", "Google Blog", "https://blog.google/a"),
        item("NVIDIA GPU benchmark 95 points H200", "NVIDIA Blog", "https://blogs.nvidia.com/a"),
    ]
    snap = {"date": "2026-10-14", "count": len(items), "items": items}
    skel = skeleton(snap)
    assert isinstance(skel["title"], str) and len(skel["title"]) > 0
    print("ok: title join regression")


if __name__ == "__main__":
    test_coverage_full()
    test_coverage_partial()
    test_coverage_miss()
    test_skeleton_main_boundary()
    test_title_join_regression()
    print("교차 평가 반영 tests passed")
