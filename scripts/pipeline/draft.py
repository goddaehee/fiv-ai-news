#!/usr/bin/env python3
"""Turn a collected snapshot into an issue JSON.

If XAI_API_KEY / GROK_API_KEY / OPENAI_API_KEY is set, ask the model to write
the Korean issue in the house voice. Otherwise write a skeleton the editor fills.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cluster import cluster, rank_buckets
from validate import check

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[2]
ISSUES = ROOT / "content" / "issues" if (ROOT / "content" / "issues").exists() else Path("content/issues")

PROMPT = """당신은 '5분 AI 뉴스' 편집장입니다. 영어 RSS 묶음을 한국어 데일리 호 JSON으로 다시 씁니다.

규칙:
- 남의 문장을 베끼지 말고, 공개된 회사·수치·날짜만 사실로 삼아 우리 문장으로 씁니다.
- 제목은 '누가 무엇을 했다' 과거형 완결 문장.
- 시사점은 입니다/됩니다. '하십시오' 금지.
- sources.url 은 입력에 있는 실제 http(s) 링크만. 없으면 공식 홈(https://openai.com 등).
- kind는 hot|talk|rt|doc. 공식 블로그·문서는 doc.
- briefing 8~10, analysis는 briefing id와 1:1, bullets 3, body 2~3문단, tips 6, keynums 6~8, timeline 5~8.
- extras 섹션 id는 extras, 제목은 '🆕 그 밖의 신기능·신제품'.
- 확인 안 된 인수는 미확정이라고 밝힙니다.
- 과장 형용사(혁명, 폭발) 금지. 숫자로 강도를 전합니다.

출력은 JSON 객체 하나만. 스키마 키: date,title,heroline,dek,tag,briefMin,readMin,briefing,keywords,mainEvent,keynums,timeline,intro,analysis,mood,tips,method.

method 고정문: "수치는 각 회사의 발표 화면과 공식 문서, 주요 매체 보도에서 가져왔습니다. 자체 측정 벤치마크와 개인 사용량 화면의 값은 본문에 그 사실을 함께 적었으며, 이 리포트는 외부 독립 검증 전입니다."
"""


def pick_key() -> tuple[str, str, str] | None:
    if os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY"):
        key = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
        return key, "https://api.x.ai/v1/chat/completions", os.environ.get("XAI_MODEL", "grok-4")
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"], "https://api.openai.com/v1/chat/completions", os.environ.get("OPENAI_MODEL", "gpt-4.1")
    return None


def chat(url: str, key: str, model: str, user: str) -> str:
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": user},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()) as res:
        data = json.loads(res.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("model did not return JSON")
    return json.loads(text[start : end + 1])


def skeleton(snap: dict) -> dict:
    date = snap["date"]
    buckets = rank_buckets(cluster(snap["items"]))
    briefing = []
    analysis = []
    timeline = []
    keynums = []
    for i, (name, items) in enumerate(buckets[:9], start=1):
        top = items[0]
        hid = name.replace("_", "-")[:24]
        headline = top["title"].rstrip(".")
        briefing.append({"id": hid, "headline": headline, "summary": (top.get("summary") or headline)[:220]})
        src = {"handle": top["source"], "url": top.get("url") or "https://example.com", "kind": top.get("kind") or "doc"}
        analysis.append(
            {
                "id": hid,
                "title": f"{i}. {headline}",
                "bullets": [
                    f"출처 {top['source']} — 공개 시점 {top.get('published') or '미상'}.",
                    "교차검증 전입니다. 공식 페이지를 열어 수치를 다시 보면 됩니다.",
                    "실무 적용은 원문 조건을 확인한 뒤.",
                ],
                "body": [
                    (top.get("summary") or headline)[:400],
                    "이 항목은 수집 파이프라인이 만든 초안입니다. 편집장이 한국어 리드·시사점·출처를 채운 뒤 발행합니다.",
                ],
                "takeaway": "공식 발표문과 1차 매체 숫자를 맞춰 본 뒤에 내부 메모에 올리면 됩니다.",
                "tags": [name],
                "sources": [src],
            }
        )
        if top.get("published"):
            timeline.append({"t": str(top["published"])[5:16].replace("T", " "), "d": headline[:80]})
        if len(keynums) < 6:
            keynums.append({"val": str(len(items)), "lab": name, "sub": "수집 묶음 크기"})
    if len(briefing) < 4:
        raise SystemExit("not enough clustered items to draft a skeleton")
    return {
        "date": date,
        "title": " · ".join(b["headline"].split()[:3] for b in briefing[:3]),
        "heroline": briefing[0]["headline"][:48],
        "dek": "수집 파이프라인 초안입니다. 교차검증 후 본문을 채우면 됩니다.",
        "tag": buckets[0][0],
        "briefMin": 3,
        "readMin": 12,
        "briefing": briefing,
        "keywords": [b[0] for b in buckets[:5]],
        "mainEvent": briefing[0]["headline"],
        "keynums": keynums[:8] or [{"val": str(snap["count"]), "lab": "수집 항목", "sub": "RSS+HN"}],
        "timeline": (timeline or [{"t": "00:00", "d": "수집"}])[:8],
        "intro": "이 파일은 자동 초안입니다. 공식 문서 숫자와 출처 URL을 채운 뒤 발행합니다.",
        "analysis": analysis,
        "mood": {
            "shift": "새 모델·정책이 같은 날에 겹치면 기본값이 바뀝니다.",
            "grow": "공개된 벤치·도입 지표는 비교 축을 하나 더 줍니다.",
            "caution": "수집 초안은 교차검증 전입니다.",
            "heat": "순위 뒤집기와 안전 논쟁은 과열 구간입니다.",
        },
        "tips": [
            {
                "title": "초안 숫자는 공식 페이지에서 다시 봅니다",
                "body": "RSS 요약은 잘립니다. 모델명·점수·일자는 회사 발표문을 연 뒤에 적으면 됩니다.",
                "via": "파이프라인",
            }
        ],
        "method": "수치는 각 회사의 발표 화면과 공식 문서, 주요 매체 보도에서 가져왔습니다. 자체 측정 벤치마크와 개인 사용량 화면의 값은 본문에 그 사실을 함께 적었으며, 이 리포트는 외부 독립 검증 전입니다.",
        "draft": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collected", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--force-skeleton", action="store_true")
    args = ap.parse_args()
    snap = json.loads(args.collected.read_text(encoding="utf-8"))
    out = args.out or (ISSUES / f"{snap['date']}.json")

    creds = None if args.force_skeleton else pick_key()
    if args.llm and not creds:
        print("no API key (XAI_API_KEY / GROK_API_KEY / OPENAI_API_KEY)", file=sys.stderr)
        return 2

    if creds:
        key, url, model = creds
        buckets = rank_buckets(cluster(snap["items"]))
        payload = {
            "date": snap["date"],
            "buckets": [
                {
                    "topic": name,
                    "n": len(items),
                    "items": [{"title": it["title"], "url": it.get("url"), "source": it["source"], "summary": it.get("summary"), "published": it.get("published")} for it in items[:6]],
                }
                for name, items in buckets[:10]
            ],
        }
        print(f"drafting with {model}…")
        raw = chat(url, key, model, json.dumps(payload, ensure_ascii=False))
        issue = extract_json(raw)
        issue["date"] = snap["date"]
    else:
        print("no API key — writing skeleton for the editor")
        issue = skeleton(snap)

    bag = check(issue)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if bag:
        print(f"wrote {out} with {len(bag)} schema warnings (editor must fix before publish):")
        for line in bag[:20]:
            print("  -", line)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
