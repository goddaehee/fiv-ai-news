#!/usr/bin/env python3
"""1주차: 누락 회귀 테스트 — 원본 헤드라인 커버율 측정.

정답셋 = 원본 헤드라인 + 독립 선정 사건.
커버율 = (메인 또는 단신으로 다룬 사건 수) / 정답셋 사건 수.
목표: 90%+.

사용법: python3 coverage.py <clone_issue.json> [--orig-url URL]
원본 헤드라인은 fiv.co.kr /news/YYYY-MM-DD에서 가져온다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import _normalize_sim, _overlap


def fetch_orig_headlines(date: str) -> list[str]:
    """원본 당일 호에서 헤드라인 추출 (제목만, 본문 아님)."""
    url = f"https://fiv.co.kr/news/{date}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")
    # h2/h3 제목 추출 (헤드라인만)
    heads = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, flags=re.S)
    out = []
    for h in heads:
        h = re.sub(r"<[^>]+>", " ", h)
        h = re.sub(r"\s+", " ", h).strip()
        if len(h) >= 10 and "5분 AI 뉴스" not in h and "지난 뉴스" not in h:
            out.append(h)
    return out[:12]


def coverage(clone: dict, orig_heads: list[str]) -> dict:
    """클론이 원본 헤드라인을 얼마나 다뤘는지."""
    clone_texts = []
    for b in clone.get("briefing") or []:
        clone_texts.append(str(b.get("headline") or "") + " " + str(b.get("summary") or ""))
    for a in clone.get("analysis") or []:
        clone_texts.append(str(a.get("title") or ""))
    clone_norm = [_normalize_sim(t) for t in clone_texts]

    covered = []
    missed = []
    for h in orig_heads:
        nh = _normalize_sim(h)
        hit = any(_overlap(nh, cn) >= 0.5 for cn in clone_norm if len(cn) >= 8)
        (covered if hit else missed).append(h)
    total = len(orig_heads)
    return {
        "total": total,
        "covered": len(covered),
        "missed": missed,
        "rate": len(covered) / total if total else 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("issue", type=Path)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    clone = json.loads(args.issue.read_text(encoding="utf-8"))
    heads = fetch_orig_headlines(args.date)
    result = coverage(clone, heads)
    print(f"커버율: {result['covered']}/{result['total']} = {result['rate']:.0%}")
    for m in result["missed"]:
        print(f"  MISS: {m[:60]}")
    return 0 if result["rate"] >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
