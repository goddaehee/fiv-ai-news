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
from select_items import select_buckets
from validate import KINDS, check

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[2]
ISSUES = ROOT / "content" / "issues" if (ROOT / "content" / "issues").exists() else Path("content/issues")

PROMPT = """당신은 '5분 AI 뉴스' 편집장입니다. 영어 RSS 묶음을 한국어 데일리 호 JSON으로 다시 씁니다.

규칙:
- 남의 문장을 베끼지 말고, 공개된 회사·수치·날짜만 사실로 삼아 우리 문장으로 씁니다. 영어 직역 금지.
- 제목은 명사형 종결 ("Grok Voice 3.0, 음성 대화 1위", "Gemini 4 Argon 일반 공개"). 반말체("~했다/내놨다/줄였다") 금지. 같은 줄에 숫자를 넣습니다.
- 헤드라인은 명사형 종결. 올바른 예: "1만 개 에이전트가 36시간 이상 버티는 구조", "악성코드 분석 업무의 시간 단축 효과". 잘못된 예: "수 시간으로" (부사격 종결), "맡습니다" (동사 종결).
- 시사점은 두 문장(판단 + 숫자 있는 다음 행동). 입니다/됩니다. '하십시오' 금지. 칸에 적으면/내부 메모 금지.
- 시사점에 템플릿 문구를 쓰지 않습니다. '오늘 확인할 변경입니다', '숫자·적용 범위·분모는 출처 문서에서 다시 보고' 같은 메타 지시문은 절대 포함하지 않습니다. 누가 무엇을 확인·결정해야 하는지 구체적인 독자와 상황으로 씁니다.
- 시사점의 문장 뼈대는 호 안에서 항목마다 다르게 만듭니다. 첫 문장(판단)은 다음 중 매번 다른 패턴을 골라 씁니다: "…가 달라진 지점입니다", "…에서 읽히는 의미는 …입니다", "…에 미칠 영향이 큽니다", "…가 중요해진 이유는 …입니다", "…가 바뀐 대목입니다". "…것이 …의미/영향입니다" 형태의 종결은 호당 1회를 넘지 않습니다.
- 둘째 문장(다음 행동)은 "…보면 됩니다"를 반복하지 않습니다. "…부터 확인하면 됩니다", "…에 반영해 두면 됩니다", "…를 비교 기준으로 삼으면 됩니다", "…를 체크리스트에 넣어 두시면 됩니다" 중 상황에 맞는 표현을 골라 씁니다. "잡아 보면 됩니다/올려 보면 됩니다/시험해 보면 됩니다" 같은 관용적 종결은 호당 1회를 넘지 않습니다.
- briefing.summary는 headline을 복사하지 않고 1~2줄로 핵심을 압축해 씁니다.
- tags는 실제 주제 태그 3개 (내부 ID·슬러그 금지).
- mainEvent는 사람이 읽는 이벤트명 (내부 ID 금지).
- tips의 title과 body는 서로 다르게 씁니다. via는 실제 출처명 (디버그 값 금지).
- 같은 시사점을 여러 칸에 복붙하지 않습니다.
- sources.url 은 입력 buckets에 있는 실제 http(s) 링크만. example.com 금지.
- briefing.id 는 영문 소문자 슬러그 (jev, claude-docs). 숫자 금지.
- mood는 문자열 금지. {"shift":"...","grow":"...","caution":"...","heat":"..."} 객체.
- kind는 hot|talk|rt|doc. 공식 블로그·문서는 doc.
- briefing 5~7 (중요도 순 선정. 뉴스가 적은 날은 3~4개도 가능 — 억지 채우기 금지), analysis는 briefing 중 메인 3~5개 id와 1:1 (나머지는 단신, analysis 없음), bullets 3, body 3문단 기본(핵심 기사는 최대 4문단, 문단당 2~3문장), tips 4~5, keynums 4~6, timeline 4~6.
- analysis는 입력의 main_topics 목록에 있는 토픽의 briefing id와 1:1로만 작성한다. main_topics에 없는 토픽으로는 analysis를 만들지 않는다 (도메인 다양성 확보).
- 깊이 슬롯: 기사마다 아래 5개를 출력 전에 스스로 셉니다. 한 기사에서 2개 이상 비우면 그 기사는 실패입니다.
  전체 슬롯의 10%를 초과해 비우면 호 전체가 폐기됩니다. "근거 없음"이라고 적어도 슬롯을 통과시키지 못합니다.
  1. what: body 첫 문단, 30자 이상.
  2. context: body 둘째 문단, 30자 이상 (배경·이전 흐름).
  3. numbers: bullets+body+takeaway 안에 아라비아 숫자 + 단위 꼴이 2개 이상.
     단위: %|배|달러|억|만|점|분|시간|일|명|개|B|M|K|million|billion|thousand|times|x.
     예: 2배, 30%, 10억, 100명, 70B, $200, 2 million, 10x.
     인정하지 않음: 두 배(한글 서수), 2024년(연도), GPT-4/Claude 3.5(모델명).
     number_mentions 후보를 우선 사용하세요. 후보가 2개 미만이면 summary 안의 다른 숫자 표현을 찾아 쓰되, 없는 숫자는 만들지 마세요. 그래도 2개에 못 미치면 있는 것만 쓰고 numbers 슬롯은 비워 두어도 됩니다(검증에서 제외됩니다).
  4. limits: 한계, 하지만, 단,, 주의, 반론, 다만, 아직, 불확실, 검증되지 중 1개 이상 포함.
  5. why: takeaway 60자 이상(두 문장), 입니다/됩니다 종결, 그리고 중요, 의미, 영향, 바뀐, 달라진 중 1개 이상 포함.
- 선별 점수제: 각 기사를 영향도(0~2: 다룬 매체 수)·새로움(0~2: 24시간 이내=2)·관련성(0~2: 수치·고유명사)·근거(0~2: 공식 출처 URL) 로 채점, 총 8점 중 5점 미만은 제외.
- 소스 쿼터: 단일 출처가 당일 전체 기사 수의 25%를 넘지 않게. 메인 기사는 출처당 1개까지. analysis 선정 시 출처 도메인이 서로 다른 기사를 우선하고, 같은 도메인이 과반을 차지하면 다른 출처의 대체 기사로 교체하라.
- 수치·주장·인용은 입력에 제공된 원문 요약(summary)과 URL 정보에서 확인된 사실만 씁니다. 해석·전망은 허용하되 사실과 구분하고, 확인 안 된 것은 '추정'·'미확정'으로 명시합니다. 이 규칙은 body뿐 아니라 intro·bullets·extra·tips·keynums·timeline 전체에 적용됩니다.
- 각 analysis는 extra 필드를 가질 수 있습니다: '그 밖에: '로 시작하는 한 문단. 본문에서 못 다룬 관련 소식이 해당 항목의 sources에 있을 때만 2~3문장으로 짧게 쓰고, 없으면 빈 문자열로 둡니다. 본문·다른 항목과 겹치지 않게.
- keynums는 3개 이상. number_mentions에서 확인된 수치만 넣습니다. sub에 '초안', '교차검증 전' 같은 문구를 적지 않습니다. 확인 안 된 수치는 keynums에 넣지 않습니다.
- intro 첫 문장은 입력 JSON의 date_ko 값으로 시작합니다(예: '10월 15일 수요일 발행.'). 이어서 오늘 호 항목에서 나온 맥락 한 문장을 붙입니다. 맥락이 없으면 날짜만 씁니다.
- timeline.t는 해당 item의 published_ko를 한 글자도 바꾸지 않고 복사합니다. 값이 없으면 그 칸을 생략합니다. "01", "02" 같은 순번을 만들지 않습니다. timeline은 3개 이상.
[작성 예시 — 형식 참고용. 숫자와 시각은 입력에 있던 값만 씁니다]
body: "A사가 새 모델을 공개했다. 응답은 2배 빨라지고 가격은 30% 내렸다.\n\n이전 모델이 기준선이었다. 다만 평가는 영어 과제뿐이라 한계가 있다."
takeaway: "응답 속도와 가격이 함께 바뀐 점이 도입 비용 판단에 중요하다. 다음 분기 적용 전에 영어 외 과제 점수도 확인하면 됩니다."
timeline: [{"t": "<그 item의 published_ko 그대로>", "d": "모델 공개"}]
keynums: [{"val": "2배", "lab": "응답 속도", "sub": "A사 발표"}]
- 전체 분량: briefMin 5, readMin은 실제 분량 기준이며 normalize에서 글자 수로 계산합니다.
- 확인 안 된 인수는 미확정이라고 밝힙니다. 회사 자체 측정은 본문에 그 사실을 적습니다.
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


def chat(url: str, key: str, model: str, user: str, *, effort: str | None = None, temperature: float = 1.0, timeout: int | None = None) -> str:
    # P7 (Grok C1): 기본 타임아웃 600 → 300으로 하향.
    # GitHub Actions step timeout(20분) 안에 3회 재시도가 들어가도록.
    # attempt별로는 main()에서 더 짧게 지정할 수 있음 (1차 300s → 2차 240s → 3차 180s).
    timeout = timeout if timeout is not None else int(os.environ.get("LLM_TIMEOUT", "300"))
    payload = {
        "model": model,
        "temperature": temperature,
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


def attach_sources(issue: dict, snap: dict, buckets: list | None = None) -> dict:
    pool: list[dict] = []
    for pair in buckets or []:
        items = pair[1] if isinstance(pair, (list, tuple)) and len(pair) == 2 else []
        pool.extend(items)
    pool.extend(snap.get("items") or [])
    seen: set[str] = set()
    uniq: list[dict] = []
    for it in pool:
        url = it.get("url") or ""
        if not url.startswith("http") or "example.com" in url or url in seen:
            continue
        seen.add(url)
        uniq.append(it)

    analyses = issue.get("analysis") or []
    bucket_list = list(buckets or [])
    for i, a in enumerate(analyses):
        srcs = a.get("sources") or []
        hollow = not srcs or all("example.com" in (s.get("url") or "") for s in srcs)
        if not hollow:
            continue
        candidates: list[dict] = []
        if i < len(bucket_list):
            candidates.extend(bucket_list[i][1][:4])
        hit = _hit(uniq, a.get("title") or "") or _hit(uniq, " ".join(a.get("bullets") or []))
        if hit:
            candidates.insert(0, hit)
        picked = []
        used: set[str] = set()
        for it in candidates + uniq[:12]:
            url = it.get("url") or ""
            if not url.startswith("http") or "example.com" in url or url in used:
                continue
            used.add(url)
            picked_src = {
                "handle": it.get("source") or "source",
                "url": url,
                "kind": it.get("kind") or "doc",
            }
            # P5: Google News <source url> 실발행처 — 검증기의 도메인 계산에 사용
            if it.get("origin_url"):
                picked_src["origin_url"] = it["origin_url"]
            picked.append(picked_src)
            if len(picked) >= 2:
                break
        if picked:
            a["sources"] = picked
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
        if not url.startswith("http") or "example.com" in url:
            continue
        kind = s.get("kind") if s.get("kind") in KINDS else "doc"
        handle = _text(s.get("handle") or s.get("name") or s.get("source") or s.get("title")) or "source"
        out.append({"handle": handle[:80], "url": url, "kind": kind})
    return out


def thicken_body(body: list[str], bullets: list[str]) -> list[str]:
    """Length is not a reason to drop a day. Expand from the section's own bullets.
    P0: 템플릿 패딩 제거 — 부족하면 짧게 두고 validate가 잡는다."""
    out = []
    for i, raw in enumerate(body or [""]):
        p = (raw or "").strip()
        if len(p) < 90 and bullets:
            extra = bullets[min(i, len(bullets) - 1)]
            if extra and extra not in p:
                p = f"{p} {extra}".strip()
        # P0: 고정 패딩 문구 추가 금지. 짧으면 짧은 대로 둔다.
        out.append(p)
    if len(out) < 2:
        out.append(" ".join(bullets[:3]))
    return [p for p in out[:6] if p]


def thicken_take(take: str, bullets: list[str], title: str) -> str:
    """P0: 삭제하지 않는다. 길이·어미 판정은 validator(check)의 몫이다.
    60~69자 takeaway나 개조식 어미가 코드에 의해 지워지면 EMPTY-001이 되므로,
    템플릿 문구(블록리스트·편집 메모)만 비우고 나머지는 그대로 둔다."""
    take = (take or "").strip().replace("하십시오", "하면 됩니다")
    # P0: 블록리스트 문구가 있으면 전체를 비운다 (기존 데이터의 템플릿 잔류 제거)
    _bl = Path(__file__).resolve().parent / "template_blocklist.txt"
    if _bl.exists():
        phrases = [l.strip() for l in _bl.read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.strip().startswith("#")]
        if any(ph in take for ph in phrases):
            take = ""
    if any(bad in take for bad in ("내부 메모에", "칸에 적", "칸을 나눠", "example.com")):
        take = ""
    return take


# P0: 검증기와 동일한 수치 정규식 — number_mentions 후보는 이 패턴을 통과한 것만.
# validate.check_depth의 numbers 슬롯과 정확히 일치해야 한다.
# P1 (Codex): AI 뉴스 실측 기반 확장. 모델명(GPT-4)·연도(2024년)는 제외.
# \b 대신 (?![0-9A-Za-z]) 사용 — \b는 한글 조사 앞에서 단어 경계로 인식하지 않음.
NUM_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|배|달러|억|만|점|분|시간|일|명|개)"  # 기존 한국어 단위
    r"|\$\d+(?:\.\d+)?\s*(?:B|M|K|billion|million)?(?![0-9A-Za-z])"  # $200, $300B
    r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:B|M|K)(?![0-9A-Za-z])"  # 70B (GPT-4 제외)
    r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:million|billion|thousand|times)(?![0-9A-Za-z])"
    r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?x(?![0-9A-Za-z])",  # 10x
    re.IGNORECASE,
)


def number_mentions(summary: str) -> list[str]:
    """summary에서 검증기를 통과하는 수치 표면만 추출 (LLM 입력용 후보).
    LLM의 수치 인식과 정규식의 차이를 메우기 위해 미리 뽑아 payload에 넣어준다.
    예: "응답은 2배 빨라지고 가격은 30% 내렸다" → ["2배", "30%"].
    P1 (Codex): findall 대신 finditer 사용 — 그룹이 있는 패턴에서 튜플 반환 문제 방지."""
    seen: list[str] = []
    for m in NUM_RE.finditer(summary or ""):
        s = m.group(0).strip()
        if s and s not in seen:
            seen.append(s)
    return seen[:6]


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
            bullets = [title]
        while len(bullets) < 2:
            bullets.append("교차검증 전입니다. 공식 페이지를 열어 수치를 다시 보면 됩니다.")
        if not body:
            body = [title]
        body = thicken_body(body, bullets)
        tags = [_text(x).strip() for x in _list(a.get("tags")) if _text(x).strip()]
        # P0: 내부 ID 폴백 금지. 비어 있으면 비운 채로 두고 validate가 판단한다.
        tags = [t for t in tags if t != hid]
        sources = _sources(a.get("sources"))
        if not sources:
            sources = []
        take = _text(a.get("takeaway") or a.get("so") or a.get("point"))
        if "하십시오" in take:
            take = take.replace("하십시오", "하면 됩니다")
        # P0: 템플릿 생성 금지. 비어 있으면 비운 채로 두고 validate가 error로 잡는다.
        take = thicken_take(take, bullets, title)
        extra = _text(a.get("extra"))
        if extra in ("없음", "해당 없음", "없습니다", "-", "—"):
            extra = ""
        if extra and not extra.startswith("그 밖에"):
            extra = f"그 밖에: {extra}"
        analysis.append(
            {
                "id": hid if hid in ids or not ids else brief[min(i - 1, len(brief) - 1)]["id"],
                "n": i,
                "title": title if title[:1].isdigit() else f"{i}. {title}",
                "bullets": bullets[:8],
                "body": body[:6],
                "extra": extra,
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
            # P0: via 디버그 값 금지. 비워 두고 validate가 error로 잡는다.
            tips.append({"title": t[:80], "body": t, "via": ""})
            continue
        if not isinstance(t, dict):
            continue
        title = _text(t.get("title") or t.get("h") or t.get("name"))
        body = _text(t.get("body") or t.get("text") or t.get("d"))
        if title and body:
            # P0: 기존 데이터의 '파이프라인' 디버그 값도 제거
            via = _text(t.get("via"))
            if via.lower() in ("파이프라인", "pipeline", "auto", "draft"):
                via = ""
            tips.append({"title": title, "body": body, "via": via})

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
                    "body": thicken_body(
                        [b["summary"] or b["headline"]],
                        [b["summary"] or b["headline"], "교차검증 전입니다. 공식 페이지를 열어 수치를 다시 보면 됩니다."],
                    ),
                    "takeaway": thicken_take("", [b["summary"] or b["headline"]], b["headline"]),
                    "tags": [b["id"]],
                    "sources": [],
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
            keynums.append({"val": val, "lab": "본문 수치", "sub": "본문"})
            if len(keynums) >= 3:
                break
    # P0: 패딩 금지. 부족하면 그대로 두고 validator가 판단한다.
    # "01"·"교차검증 전" 같은 가짜 값으로 fail-closed 게이트를 속이지 않는다.
    if not tips:
        tips.append(
            {
                "title": "초안 숫자는 공식 페이지에서 다시 봅니다",
                "body": "RSS 요약은 잘립니다. 모델명·점수·일자는 회사 발표문을 연 뒤에 적으면 됩니다.",
                "via": "",
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

    def _read_mins() -> tuple[int, int]:
        # 읽기 시간은 LLM 선언이 아니라 실제 글자 수로 계산 (분당 500자)
        brief_chars = sum(len(b["headline"]) + len(b["summary"]) for b in brief)
        total_chars = (
            brief_chars
            + len(_text(issue.get("intro")))
            + sum(len(p) for a in analysis for p in a["body"])
            + sum(len(a["takeaway"]) + len(a.get("extra") or "") for a in analysis)
            + sum(len(t["title"]) + len(t["body"]) for t in tips)
        )
        brief_min = min(7, max(3, round(brief_chars / 500)))
        read_min = min(15, max(5, round(total_chars / 500)))
        return brief_min, read_min

    _brief_min, _read_min = _read_mins()

    out = {
        "date": _text(issue.get("date")),
        "title": _text(issue.get("title")) or (brief[0]["headline"] if brief else "초안"),
        "heroline": _text(issue.get("heroline")) or (brief[0]["headline"][:48] if brief else "초안"),
        "dek": _text(issue.get("dek")) or (brief[0]["summary"] if brief else "수집 파이프라인 초안입니다."),
        "tag": _text(issue.get("tag")) or (keywords[0] if keywords else "AI"),
        "briefMin": _brief_min,
        "readMin": _read_min,
        "briefing": brief,
        "keywords": keywords[:8],
        "mainEvent": (
            lambda me=(_text(issue.get("mainEvent")) or ""): (
                # P0: 내부 ID면 headline으로 폴백. 비어 있으면 비운 채로 validate가 판단.
                (brief[0]["headline"] if brief else "")
                if (me in {b["id"] for b in brief if isinstance(b, dict)})
                or not (len(me) >= 12)
                else me
            )
        )(),
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
    ranked = rank_buckets(cluster(snap["items"]))
    # 1주차: 선별 점수제 + 소스 쿼터. 메인 3~5개는 briefing+analysis, 나머지는 briefing만 (단신).
    main_buckets, rest_buckets = select_buckets(ranked)
    buckets = [(n, it) for n, it, _ in main_buckets] + [(n, it) for n, it, _ in rest_buckets]
    main_names = {n for n, _, _ in main_buckets}
    briefing = []
    analysis = []
    timeline = []
    keynums = []
    for i, (name, items) in enumerate(buckets[:9], start=1):
        top = items[0]
        hid = name.replace("_", "-")[:24]
        headline = top["title"].rstrip(".")
        briefing.append({"id": hid, "headline": headline, "summary": (top.get("summary") or headline)[:220]})
        if name not in main_names:
            continue  # 단신: briefing만, analysis 없음
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
        "title": " · ".join(" ".join(b["headline"].split()[:3]) for b in briefing[:3]),
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
                "via": "",
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
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--attempt", type=int, default=1)
    args = ap.parse_args()
    snap = json.loads(args.collected.read_text(encoding="utf-8"))
    out = args.out or (ISSUES / f"{snap['date']}.json")
    pipe = args.collected.parent

    creds = None if args.force_skeleton else pick_key(args.provider)
    if args.llm and not creds:
        print("no API key (GLM_API_KEY / XAI_API_KEY / OPENAI_API_KEY)", file=sys.stderr)
        return 2

    if creds:
        name, key, url, model = creds
        ranked = rank_buckets(cluster(snap["items"]))
        # P4: 프로덕션 LLM 경로에도 select_buckets 배선 (도메인 다양성 확보).
        # 기존에는 skeleton() 폴백에서만 호출되어 LLM 경로에서는 선별이 동작하지 않았다.
        main_buckets, rest_buckets = select_buckets(ranked)
        buckets = [(t, items) for t, items, _s in main_buckets + rest_buckets]
        dt = datetime.strptime(snap["date"], "%Y-%m-%d")
        weekday_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][dt.weekday()]
        date_ko = f"{dt.month}월 {dt.day}일 {weekday_ko}"

        def _published_ko(pub: str | None) -> str | None:
            # "2026-10-10T20:30+09:00" (KST) → "10/10 20:30". LLM이 타임존 계산을 하지 않게 미리 변환.
            if not pub:
                return None
            m = re.match(r"^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})", str(pub))
            if not m:
                return None
            return f"{m.group(1)}/{m.group(2)} {m.group(3)}:{m.group(4)}"

        def _item_payload(it: dict) -> dict:
            # P1 (Codex): 후보는 420자 전체 summary에서 추출 (180자 잘림 전에).
            # LLM에게는 180자만 보여주지만 쓸 수 있는 숫자는 전체에서 뽑는다.
            full_summary = it.get("summary") or ""
            summary = full_summary[:180]
            return {
                "title": it["title"],
                "url": it.get("url"),
                "source": it["source"],
                "summary": summary,
                "published": it.get("published"),
                "published_ko": _published_ko(it.get("published")),
                # P0: LLM이 쓸 수 있는 수치 후보 — 검증기 numbers 정규식을 통과한 것만.
                "number_mentions": number_mentions(full_summary),
            }

        payload = {
            "date": snap["date"],
            "date_ko": date_ko,
            # P4: analysis는 main_topics의 토픽(briefing id)과 1:1로만 작성.
            # main이 먼저 오도록 buckets도 main+rest 순으로 정렬됨.
            "main_topics": [topic for topic, _items, _s in main_buckets],
            "buckets": [
                {
                    "topic": topic,
                    "n": len(items),
                    "items": [_item_payload(it) for it in items[:3]],
                }
                for topic, items in buckets[:7]
            ],
        }
        print(f"drafting provider={name} model={model} buckets={len(payload['buckets'])} temp={args.temperature}", flush=True)
        # P7: attempt별 타임아웃 단축 — 3회가 20분 step 안에 들어가도록.
        # 1차 300s, 2차 240s, 3차 180s. LLM_TIMEOUT 환경변수가 설정되면 그것을 우선 사용.
        _attempt_timeouts = {1: 300, 2: 240, 3: 180}
        _env_to = os.environ.get("LLM_TIMEOUT")
        _to = int(_env_to) if _env_to else _attempt_timeouts.get(args.attempt, 180)
        try:
            raw = chat(url, key, model, json.dumps(payload, ensure_ascii=False), temperature=args.temperature, timeout=_to)
        except TimeoutError as e:
            print(f"{e}; retrying with reasoning_effort=low", flush=True)
            raw = chat(url, key, model, json.dumps(payload, ensure_ascii=False), effort="low", temperature=args.temperature, timeout=_to)
        # 디버깅용: 원시 LLM 응답 저장 (시도별 분리, 잘림 vs 나쁜 샘플 구분)
        try:
            raw_path = pipe / f"{snap['date']}.raw-llm.attempt{args.attempt}.txt"
            raw_path.write_text(raw, encoding="utf-8")
        except Exception:
            pass
        issue = extract_json(raw)
        issue["date"] = snap["date"]
        issue = normalize(issue)
        issue["date"] = snap["date"]
        issue = attach_sources(issue, snap, buckets)
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
