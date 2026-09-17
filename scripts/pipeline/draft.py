#!/usr/bin/env python3
"""Turn a collected snapshot into an issue JSON.

If XAI / GLM / OpenAI key is set, ask the model to write the Korean issue.
Otherwise write a skeleton the editor fills.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cluster import cluster, rank_buckets
from validate import KINDS, check

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[2]
ISSUES = ROOT / "content" / "issues" if (ROOT / "content" / "issues").exists() else Path("content/issues")

PROMPT = """당신은 '5분 AI 뉴스' 편집장입니다. 영어 RSS 묶음을 한국어 데일리 호 JSON으로 다시 씁니다.

규칙:
- 남의 문장을 베끼지 말고, 공개된 회사·수치·날짜만 사실로 삼아 우리 문장으로 씁니다.
- 제목은 '누가 무엇을 했다' 과거형 완결 문장.
- 시사점은 입니다/됩니다. '하십시오' 금지.
- sources.url 은 입력 buckets에 있는 실제 http(s) 링크만. example.com 금지.
- briefing.id 는 영문 소문자 슬러그 (jev, claude-docs). 숫자 금지.
- mood는 문자열 금지. {"shift":"...","grow":"...","caution":"...","heat":"..."} 객체.
- kind는 hot|talk|rt|doc. 공식 블로그·문서는 doc.
- briefing 8~10, analysis는 briefing id와 1:1, bullets 3, body 2~3문단, tips 6, keynums 6~8, timeline 5~8.
- extras 섹션 id는 extras, 제목은 '🆕 그 밖의 신기능·신제품'.
- 확인 안 된 인수는 미확정이라고 밝힙니다.
- 과장 형용사(혁명, 폭발) 금지. 숫자로 강도를 전합니다.

출력은 JSON 객체 하나만. 스키마 키: date,title,heroline,dek,tag,briefMin,readMin,briefing,keywords,mainEvent,keynums,timeline,intro,analysis,mood,tips,method.

method 고정문: "수치는 각 회사의 발표 화면과 공식 문서, 주요 매체 보도에서 가져왔습니다. 자체 측정 벤치마크와 개인 사용량 화면의 값은 본문에 그 사실을 함께 적었으며, 이 리포트는 외부 독립 검증 전입니다."
"""


PROVIDERS = {
    "xai": {
        "env": ("XAI_API_KEY", "GROK_API_KEY"),
        "url_env": "XAI_BASE_URL",
        "url": "https://api.x.ai/v1/chat/completions",
        "model_env": "XAI_MODEL",
        "model": "grok-4",
    },
    "glm": {
        "env": ("GLM_API_KEY", "ZHIPU_API_KEY", "ZHIPUAI_API_KEY"),
        "url_env": "GLM_BASE_URL",
        "url": "https://api.z.ai/api/paas/v4/chat/completions",
        "model_env": "GLM_MODEL",
        "model": "glm-5.3",
    },
    "openai": {
        "env": ("OPENAI_API_KEY",),
        "url_env": "OPENAI_BASE_URL",
        "url": "https://api.openai.com/v1/chat/completions",
        "model_env": "OPENAI_MODEL",
        "model": "gpt-4.1",
    },
}


def pick_key(prefer: str | None = None) -> tuple[str, str, str, str] | None:
    order = ["xai", "glm", "openai"]
    want = (prefer or os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if want in PROVIDERS:
        order = [want] + [p for p in order if p != want]
    for name in order:
        spec = PROVIDERS[name]
        key = next((os.environ[k].strip() for k in spec["env"] if os.environ.get(k) and os.environ[k].strip()), None)
        if not key:
            continue
        url = (os.environ.get(spec["url_env"]) or spec["url"]).strip()
        if not url.endswith("/chat/completions"):
            url = url.rstrip("/") + "/chat/completions"
        model = (os.environ.get(spec["model_env"]) or spec["model"]).strip()
        return name, key, url, model
    return None


def chat(url: str, key: str, model: str, user: str, *, effort: str | None = None) -> str:
    timeout = int(os.environ.get("LLM_TIMEOUT", "600"))
    payload = {
        "model": model,
        "temperature": 1.0,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": user},
        ],
    }
    if model.lower().startswith("glm-5"):
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = effort or os.environ.get("GLM_REASONING", "low")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"LLM HTTP {e.code} from {url.split('?')[0]} model={model}: {detail}") from e
    except TimeoutError as e:
        raise TimeoutError(f"LLM timed out after {timeout}s ({url.split('?')[0]} model={model})") from e
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content") or ""


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


def slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", (s or "").lower()).strip("-")
    return (s[:36] or "s")


def _hit(items: list[dict], title: str) -> dict | None:
    words = [w for w in re.split(r"\W+", (title or "").lower()) if len(w) > 3][:8]
    if not words:
        return None
    best, score = None, 0
    for it in items:
        blob = f"{it.get('title') or ''} {it.get('summary') or ''}".lower()
        sc = sum(1 for w in words if w in blob)
        if sc > score:
            best, score = it, sc
    return best if score >= 2 else None


def attach_sources(issue: dict, snap: dict) -> dict:
    items = [it for it in (snap.get("items") or []) if (it.get("url") or "").startswith("http")]
    for a in issue.get("analysis") or []:
        srcs = a.get("sources") or []
        hollow = not srcs or all("example.com" in (s.get("url") or "") for s in srcs)
        if not hollow:
            continue
        hit = _hit(items, a.get("title") or "") or _hit(items, " ".join(a.get("bullets") or []))
        if hit:
            a["sources"] = [{"handle": hit["source"], "url": hit["url"], "kind": hit.get("kind") or "doc"}]
    return issue


MOOD_KEYS = ("shift", "grow", "caution", "heat")
DEFAULT_MOOD = {
    "shift": "새 모델·정책이 같은 날에 겹치면 기본값이 바뀝니다.",
    "grow": "공개된 벤치·도입 지표는 비교 축을 하나 더 줍니다.",
    "caution": "수집 초안은 교차검증 전입니다.",
    "heat": "순위 뒤집기와 안전 논쟁은 과열 구간입니다.",
}


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return " ".join(_text(x) for x in v if _text(x))
    if isinstance(v, dict):
        return _text(v.get("text") or v.get("body") or v.get("value") or next(iter(v.values()), ""))
    return str(v).strip()


def _list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        parts = [p.strip(" -•\t") for p in v.split("\n") if p.strip()]
        return parts or [v.strip()]
    return [v]


def _mood(v) -> dict:
    out = dict(DEFAULT_MOOD)
    if isinstance(v, dict):
        for k in MOOD_KEYS:
            t = _text(v.get(k))
            if t:
                out[k] = t
        return out
    if isinstance(v, str) and v.strip():
        out["shift"] = v.strip()
        return out
    if isinstance(v, list):
        for k, item in zip(MOOD_KEYS, v):
            t = _text(item)
            if t:
                out[k] = t
        return out
    return out


def _sources(v) -> list[dict]:
    out = []
    for s in _list(v):
        if isinstance(s, str):
            url = s.strip()
            if url.startswith("http"):
                out.append({"handle": "source", "url": url, "kind": "doc"})
            continue
        if not isinstance(s, dict):
            continue
        url = _text(s.get("url") or s.get("href") or s.get("link"))
        if not url.startswith("http"):
            continue
        kind = s.get("kind") if s.get("kind") in KINDS else "doc"
        handle = _text(s.get("handle") or s.get("name") or s.get("source") or s.get("title")) or "source"
        out.append({"handle": handle[:80], "url": url, "kind": kind})
    return out


def normalize(issue: dict) -> dict:
    """Coerce sloppy LLM JSON into the house schema so check() does not crash."""
    brief = []
    for i, b in enumerate(_list(issue.get("briefing")), start=1):
        if isinstance(b, str):
            b = {"headline": b}
        if not isinstance(b, dict):
            continue
        hid = _text(b.get("id"))
        headline = _text(b.get("headline") or b.get("title"))
        if not hid or hid.isdigit() or len(hid) < 3:
            hid = slug(headline or f"s{i}")
        hid = hid.replace(" ", "-")[:40]
        brief.append(
            {
                "id": hid,
                "headline": headline or hid,
                "summary": _text(b.get("summary") or b.get("dek") or headline)[:400],
            }
        )
    ids = {b["id"] for b in brief}

    analysis = []
    for i, a in enumerate(_list(issue.get("analysis")), start=1):
        if isinstance(a, str):
            a = {"title": a, "body": [a]}
        if not isinstance(a, dict):
            continue
        hid = _text(a.get("id")) or (brief[i - 1]["id"] if i - 1 < len(brief) else f"s{i}")
        title = _text(a.get("title") or a.get("headline")) or hid
        bullets = [_text(x) for x in _list(a.get("bullets")) if _text(x)]
        body = [_text(x) for x in _list(a.get("body")) if _text(x)]
        if not bullets:
            bullets = [title, "교차검증 전입니다. 공식 페이지를 열어 수치를 다시 보면 됩니다."]
        if not body:
            body = [title]
        tags = [_text(x) for x in _list(a.get("tags")) if _text(x)] or [hid]
        sources = _sources(a.get("sources"))
        if not sources:
            sources = [{"handle": "source", "url": "https://example.com", "kind": "doc"}]
        take = _text(a.get("takeaway") or a.get("so") or a.get("point"))
        if "하십시오" in take:
            take = take.replace("하십시오", "하면 됩니다")
        if not take:
            take = body[-1] if body else "공식 발표문과 1차 매체 숫자를 맞춰 본 뒤에 내부 메모에 올리면 됩니다."
        analysis.append(
            {
                "id": hid if hid in ids or not ids else brief[min(i - 1, len(brief) - 1)]["id"],
                "n": i,
                "title": title if title[:1].isdigit() else f"{i}. {title}",
                "bullets": bullets[:8],
                "body": body[:6],
                "takeaway": take,
                "tags": tags[:6],
                "sources": sources[:6],
            }
        )

    keynums = []
    for k in _list(issue.get("keynums") or issue.get("keyNumbers")):
        if not isinstance(k, dict):
            continue
        val = _text(k.get("val") or k.get("value") or k.get("num"))
        lab = _text(k.get("lab") or k.get("label") or k.get("name"))
        sub = _text(k.get("sub") or k.get("note") or k.get("source"))
        if val and lab:
            keynums.append({"val": val, "lab": lab, "sub": sub or lab})

    timeline = []
    for t in _list(issue.get("timeline")):
        if not isinstance(t, dict):
            continue
        when = _text(t.get("t") or t.get("time") or t.get("date") or t.get("when"))
        d = _text(t.get("d") or t.get("event") or t.get("text") or t.get("what"))
        if when and d:
            timeline.append({"t": when, "d": d})

    tips = []
    for t in _list(issue.get("tips")):
        if isinstance(t, str):
            tips.append({"title": t[:80], "body": t, "via": "파이프라인"})
            continue
        if not isinstance(t, dict):
            continue
        title = _text(t.get("title") or t.get("h") or t.get("name"))
        body = _text(t.get("body") or t.get("text") or t.get("d"))
        if title and body:
            tips.append({"title": title, "body": body, "via": _text(t.get("via")) or "파이프라인"})

    if len(analysis) < 2:
        have = {x["id"] for x in analysis}
        for b in brief:
            if b["id"] in have:
                continue
            analysis.append(
                {
                    "id": b["id"],
                    "n": len(analysis) + 1,
                    "title": f"{len(analysis)+1}. {b['headline']}",
                    "bullets": [b["summary"] or b["headline"], "교차검증 전입니다. 공식 페이지를 열어 수치를 다시 보면 됩니다."],
                    "body": [b["summary"] or b["headline"]],
                    "takeaway": "공식 발표문과 1차 매체 숫자를 맞춰 본 뒤에 내부 메모에 올리면 됩니다.",
                    "tags": [b["id"]],
                    "sources": [{"handle": "source", "url": "https://example.com", "kind": "doc"}],
                }
            )
            if len(analysis) >= 2:
                break
    if keynums and all(str(k["val"]).isdigit() and str(k["lab"]).isdigit() for k in keynums):
        keynums = []
    if len(keynums) < 3:
        blob = " ".join(f"{b['headline']} {b['summary']}" for b in brief)
        seen = {k["val"] for k in keynums}
        for m in re.finditer(r"(\$[\d,.]+|\d+(?:\.\d+)?%|\d{1,3}(?:,\d{3})+)", blob):
            val = m.group(1)
            if val in seen:
                continue
            seen.add(val)
            keynums.append({"val": val, "lab": "본문 수치", "sub": "초안 · 교차검증 전"})
            if len(keynums) >= 3:
                break
    while len(keynums) < 3 and brief:
        b = brief[len(keynums) % len(brief)]
        if any(k["lab"] == b["headline"][:24] for k in keynums):
            break
        keynums.append({"val": "—", "lab": b["headline"][:24], "sub": "교차검증 전"})
    while len(timeline) < 3:
        timeline.append({"t": f"0{len(timeline)+1}", "d": (brief[0]["headline"] if brief else "수집")[:80]})
    if not tips:
        tips.append(
            {
                "title": "초안 숫자는 공식 페이지에서 다시 봅니다",
                "body": "RSS 요약은 잘립니다. 모델명·점수·일자는 회사 발표문을 연 뒤에 적으면 됩니다.",
                "via": "파이프라인",
            }
        )

    keywords = [_text(x) for x in _list(issue.get("keywords")) if _text(x)]
    if len(keywords) < 3:
        keywords = [b["id"] for b in brief[:5]] or ["AI", "모델", "정책"]

    def _int(v, default: int) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    out = {
        "date": _text(issue.get("date")),
        "title": _text(issue.get("title")) or (brief[0]["headline"] if brief else "초안"),
        "heroline": _text(issue.get("heroline")) or (brief[0]["headline"][:48] if brief else "초안"),
        "dek": _text(issue.get("dek")) or (brief[0]["summary"] if brief else "수집 파이프라인 초안입니다."),
        "tag": _text(issue.get("tag")) or (keywords[0] if keywords else "AI"),
        "briefMin": _int(issue.get("briefMin"), 5),
        "readMin": _int(issue.get("readMin"), 14),
        "briefing": brief,
        "keywords": keywords[:8],
        "mainEvent": (
            _text(issue.get("mainEvent"))
            if len(_text(issue.get("mainEvent"))) >= 12 and not _text(issue.get("mainEvent")).isdigit()
            else (brief[0]["headline"] if brief else "")
        ),
        "keynums": keynums,
        "timeline": timeline,
        "intro": _text(issue.get("intro")) or "이 파일은 자동 초안입니다. 공식 문서 숫자와 출처 URL을 채운 뒤 발행합니다.",
        "analysis": analysis,
        "mood": _mood(issue.get("mood")),
        "tips": tips,
        "method": _text(issue.get("method"))
        or "수치는 각 회사의 발표 화면과 공식 문서, 주요 매체 보도에서 가져왔습니다. 자체 측정 벤치마크와 개인 사용량 화면의 값은 본문에 그 사실을 함께 적었으며, 이 리포트는 외부 독립 검증 전입니다.",
        "draft": True,
    }
    return out


def published_lock(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return not cur.get("draft")


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
    ap.add_argument("--provider", choices=["xai", "glm", "openai"])
    ap.add_argument("--force-skeleton", action="store_true")
    args = ap.parse_args()
    snap = json.loads(args.collected.read_text(encoding="utf-8"))
    out = args.out or (ISSUES / f"{snap['date']}.json")

    creds = None if args.force_skeleton else pick_key(args.provider)
    if args.llm and not creds:
        print("no API key (GLM_API_KEY / XAI_API_KEY / OPENAI_API_KEY)", file=sys.stderr)
        return 2

    if creds:
        name, key, url, model = creds
        buckets = rank_buckets(cluster(snap["items"]))
        payload = {
            "date": snap["date"],
            "buckets": [
                {
                    "topic": topic,
                    "n": len(items),
                    "items": [
                        {
                            "title": it["title"],
                            "url": it.get("url"),
                            "source": it["source"],
                            "summary": (it.get("summary") or "")[:180],
                            "published": it.get("published"),
                        }
                        for it in items[:3]
                    ],
                }
                for topic, items in buckets[:8]
            ],
        }
        print(f"drafting provider={name} model={model} buckets={len(payload['buckets'])}", flush=True)
        try:
            raw = chat(url, key, model, json.dumps(payload, ensure_ascii=False))
        except TimeoutError as e:
            print(f"{e}; retrying with reasoning_effort=low", flush=True)
            raw = chat(url, key, model, json.dumps(payload, ensure_ascii=False), effort="low")
        issue = extract_json(raw)
        issue["date"] = snap["date"]
        issue = normalize(issue)
        issue["date"] = snap["date"]
        issue = attach_sources(issue, snap)
        issue["draft"] = True
    else:
        print("no API key — writing skeleton for the editor")
        issue = skeleton(snap)

    if published_lock(out):
        sidecar = ROOT / "content" / "pipeline" / f"{snap['date']}.draft.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        print(f"keeping published {out.name}; writing sidecar {sidecar}")
        out = sidecar

    bag = check(issue)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if bag:
        print(f"wrote {out} with {len(bag)} schema warnings (editor must fix before publish):")
        for line in bag[:20]:
            print("  -", line)
        return 0 if issue.get("analysis") and issue.get("briefing") else 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
