#!/usr/bin/env python3
"""Validate an issue JSON against the local schema (no extra deps)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URI_RE = re.compile(r"^https?://")
KINDS = {"hot", "talk", "rt", "doc"}
KST = timezone(timedelta(hours=9))

# --- P0: 출력 정리 검사 (TPL/ID/DUP/VIA/RND) ---
_BLOCKLIST_PATH = Path(__file__).resolve().parent / "template_blocklist.txt"
_TPL_PHRASES: list[str] = [
    l.strip() for l in _BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines()
    if l.strip() and not l.strip().startswith("#")
] if _BLOCKLIST_PATH.exists() else []

# 조사 제거용 (최장 일치 우선)
_PARTICLES = sorted(
    ["에서", "으로", "로", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도"],
    key=len, reverse=True,
)
_PUNCT_RE = re.compile(r"[^\w\s가-힣]", re.UNICODE)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)+$")


def _normalize_sim(s: str) -> str:
    """유사도 비교용 정규화: 소문자 → 구두점 제거 → 토큰 끝 조사 제거 → 공백 없이 결합."""
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    out: list[str] = []
    for tok in s.split():
        for p in _PARTICLES:
            if len(tok) > len(p) + 1 and tok.endswith(p):
                tok = tok[: -len(p)]
                break
        out.append(tok)
    return "".join(out)


def _bigrams(s: str) -> set[str]:
    return {s[i : i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else set()


def _overlap(a: str, b: str) -> float:
    """overlap coefficient = |A∩B| / min(|A|,|B|) — 포함 관계 탐지용."""
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))


def _jaccard(a: str, b: str) -> float:
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def check_p0(
    issue: dict, prev: dict | None
) -> tuple[list[str], list[str]]:
    """P0 출력 정리 게이트. (errors, warnings) — errors는 발행 차단."""
    errors: list[str] = []
    warnings: list[str] = []

    briefing = issue.get("briefing") or []
    analysis = issue.get("analysis") or []
    tips = issue.get("tips") or []

    # 내부 ID 레지스트리: 이번 호 + 이전 호 briefing ID
    id_reg: set[str] = set()
    for b in briefing:
        if isinstance(b, dict) and b.get("id"):
            id_reg.add(str(b["id"]))
    if prev:
        for b in prev.get("briefing") or []:
            if isinstance(b, dict) and b.get("id"):
                id_reg.add(str(b["id"]))

    def is_internal_id(v: str) -> bool:
        return bool(v) and v in id_reg

    # TPL-001: 시사점·본문에 템플릿 문구
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        text = str(a.get("takeaway") or "") + " " + " ".join(a.get("body") or [])
        for ph in _TPL_PHRASES:
            if ph and ph in text:
                errors.append(f"TPL-001 analysis[{i}].takeaway/body: 템플릿 문구 '{ph[:30]}'")
                break

    # ID-001: mainEvent에 내부 ID (slug 패턴도 error로 승격)
    me = str(issue.get("mainEvent") or "")
    if is_internal_id(me):
        errors.append(f"ID-001 mainEvent: 내부 ID '{me}' 노출")
    elif me and _SLUG_RE.match(me):
        errors.append(f"ID-001 mainEvent: slug 패턴 '{me}' (내부 ID 의심)")

    # DUP-001: briefing summary ≒ headline
    for i, b in enumerate(briefing):
        if not isinstance(b, dict):
            continue
        h, s = str(b.get("headline") or ""), str(b.get("summary") or "")
        nh, ns = _normalize_sim(h), _normalize_sim(s)
        if len(nh) >= 8 and len(ns) >= 8:
            if max(len(nh), len(ns)) / min(len(nh), len(ns)) <= 3:
                if _overlap(nh, ns) >= 0.9:
                    errors.append(f"DUP-001 briefing[{i}].summary: headline과 거의 동일")

    # ID-002: tags에 내부 ID / 빈 원소 (slug 패턴도 error로 승격)
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        for t in a.get("tags") or []:
            ts = str(t or "")
            if not ts.strip():
                errors.append(f"ID-002 analysis[{i}].tags: 빈 태그")
            elif is_internal_id(ts):
                errors.append(f"ID-002 analysis[{i}].tags: 내부 ID '{ts}'")
            elif _SLUG_RE.match(ts):
                errors.append(f"ID-002 analysis[{i}].tags: slug 패턴 '{ts}'")

    # DUP-002: tips title ≒ body
    for i, t in enumerate(tips):
        if not isinstance(t, dict):
            continue
        ti, bo = str(t.get("title") or ""), str(t.get("body") or "")
        nti, nbo = _normalize_sim(ti), _normalize_sim(bo)
        if len(nti) >= 8 and len(nbo) >= 8:
            if max(len(nti), len(nbo)) / min(len(nti), len(nbo)) <= 3:
                if _overlap(nti, nbo) >= 0.9:
                    errors.append(f"DUP-002 tips[{i}]: title과 body가 거의 동일")

    # VIA-001: via 디버그 값 (허용: URL 도메인 또는 알려진 출처명)
    _VIA_DEBUG = {"파이프라인", "pipeline", "auto", "draft", "normalize", "todo"}
    for i, t in enumerate(tips):
        if not isinstance(t, dict):
            continue
        via = str(t.get("via") or "").strip()
        if not via:
            errors.append(f"VIA-001 tips[{i}].via: 비어 있음")
        elif via.lower() in _VIA_DEBUG:
            errors.append(f"VIA-001 tips[{i}].via: 디버그 값 '{via}'")

    # TAKEAWAY-DUP: 시사점 템플릿 반복 방지 (클러스터 기반)
    # 3개 이상이 서로 유사(0.8+)하면 템플릿으로 판정
    takeaways = []
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        tw = str(a.get("takeaway") or "").strip()
        if tw:
            takeaways.append((i, _normalize_sim(tw)))
    if len(takeaways) >= 3:
        # 각 takeaway마다 자신과 유사한 것들의 집합을 구함
        n = len(takeaways)
        similar_to = [set() for _ in range(n)]
        for x in range(n):
            for y in range(x + 1, n):
                if _overlap(takeaways[x][1], takeaways[y][1]) >= 0.8:
                    similar_to[x].add(y)
                    similar_to[y].add(x)
        # 가장 큰 유사 클러스터 찾기 (자신 포함)
        max_cluster = 0
        for x in range(n):
            cluster = {x} | similar_to[x]
            # 클러스터 내 모든 쌍이 유사한지 확인 (clique)
            is_clique = True
            members = list(cluster)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    if members[j] not in similar_to[members[i]]:
                        is_clique = False
                        break
                if not is_clique:
                    break
            if is_clique:
                max_cluster = max(max_cluster, len(cluster))
        if max_cluster >= 3:
            errors.append(f"TAKEAWAY-DUP: 시사점 {max_cluster}개가 서로 유사 — 템플릿 반복 의심")

    # DUP-003: 섹션 간 문장 반복 (warning)
    def split_sentences(text: str) -> list[str]:
        parts = re.split(r"[.!?\n]+", text)
        return [p.strip() for p in parts if len(p.strip()) >= 20]

    seen_sents: list[tuple[str, str]] = []  # (norm, where)
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        blob = " ".join(a.get("body") or []) + " " + str(a.get("takeaway") or "")
        for s in split_sentences(blob):
            ns = _normalize_sim(s)
            if len(ns) < 20:
                continue
            for ps, where in seen_sents:
                if _jaccard(ns, ps) >= 0.85:
                    warnings.append(f"DUP-003: 문장 반복 ({where} ↔ analysis[{i}])")
                    break
            else:
                seen_sents.append((ns, f"analysis[{i}]"))
                continue
            break

    # RND-001: 빈 해시태그 렌더 (warning — 프론트 방어와 함께)
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        tags = a.get("tags") or []
        if isinstance(tags, list) and not any(str(t or "").strip() for t in tags):
            warnings.append(f"RND-001 analysis[{i}].tags: 전부 비어 있음 (빈 해시태그 렌더)")

    # EMPTY-001: 빈 시사점 (error — 템플릿 제거 후 빈값이 되면 발행 차단)
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        if not str(a.get("takeaway") or "").strip():
            errors.append(f"EMPTY-001 analysis[{i}].takeaway: 비어 있음")

    # EMPTY-002: 빈 본문 (error)
    for i, a in enumerate(analysis):
        if not isinstance(a, dict):
            continue
        body = a.get("body") or []
        btext = " ".join(body) if isinstance(body, list) else str(body)
        if not btext.strip():
            errors.append(f"EMPTY-002 analysis[{i}].body: 비어 있음")

    return errors, warnings
VOICE_BAN = (
    "하십시오",
    "칸에 적",
    "칸을 나눠",
    "내부 메모에",
    "공식 발표문과 1차 매체 숫자를 맞춰 본 뒤에",
)


def err(path: str, msg: str, bag: list[str]) -> None:
    bag.append(f"{path}: {msg}")


def require(obj: dict, keys: list[str], path: str, bag: list[str]) -> None:
    for k in keys:
        if k not in obj:
            err(path, f"missing {k}", bag)


def check(issue: dict) -> list[str]:
    bag: list[str] = []
    require(
        issue,
        [
            "date",
            "title",
            "heroline",
            "dek",
            "tag",
            "briefMin",
            "readMin",
            "briefing",
            "keywords",
            "mainEvent",
            "keynums",
            "timeline",
            "intro",
            "analysis",
            "mood",
            "tips",
            "method",
        ],
        "$",
        bag,
    )
    if not DATE_RE.match(str(issue.get("date", ""))):
        err("date", "YYYY-MM-DD required", bag)
    if not (3 <= len(issue.get("briefing") or []) <= 14):
        err("briefing", "need 3–14 items", bag)
    if not (3 <= len(issue.get("keynums") or []) <= 16):
        err("keynums", "need 3–16 items", bag)
    if len(issue.get("timeline") or []) < 3:
        err("timeline", "need ≥3", bag)
    if not (2 <= len(issue.get("analysis") or []) <= 14):
        err("analysis", "need 2–14", bag)
    if len(issue.get("tips") or []) < 1:
        err("tips", "need ≥1", bag)
    mood = issue.get("mood")
    if not isinstance(mood, dict):
        err("mood", "must be an object with shift/grow/caution/heat", bag)
        mood = {}
    for k in ("shift", "grow", "caution", "heat"):
        if not mood.get(k):
            err("mood", f"missing {k}", bag)

    ids = []
    for i, b in enumerate(issue.get("briefing") or []):
        if not isinstance(b, dict):
            err(f"briefing[{i}]", "must be object", bag)
            continue
        require(b, ["id", "headline", "summary"], f"briefing[{i}]", bag)
        ids.append(b.get("id"))
        # P0: 헤드라인 반말체 금지 (명사형 종결). "~했다/내놨다/줄였다" 등
        hl = str(b.get("headline") or "")
        if re.search(r"(했다|했다\.|내놨다|줄였다|늘렸다|낮췄다|높였다|도입했다|공개했다|발표했다|묶었다)\s*$", hl):
            err(f"briefing[{i}].headline", "반말체 종결 금지 — 명사형으로", bag)
    for i, a in enumerate(issue.get("analysis") or []):
        p = f"analysis[{i}]"
        if not isinstance(a, dict):
            err(p, "must be object", bag)
            continue
        require(a, ["id", "title", "bullets", "body", "takeaway", "tags", "sources"], p, bag)
        if len(a.get("bullets") or []) < 2:
            err(p + ".bullets", "need ≥2", bag)
        if len(a.get("body") or []) < 1:
            err(p + ".body", "need ≥1", bag)
        if len(a.get("sources") or []) < 1:
            err(p + ".sources", "need ≥1", bag)
        for j, s in enumerate(a.get("sources") or []):
            if not isinstance(s, dict):
                err(f"{p}.sources[{j}]", "must be object", bag)
                continue
            if s.get("kind") not in KINDS:
                err(f"{p}.sources[{j}].kind", "hot|talk|rt|doc", bag)
            url = str(s.get("url") or "")
            if not URI_RE.match(url):
                err(f"{p}.sources[{j}].url", "http(s) url", bag)
            if "example.com" in url:
                err(f"{p}.sources[{j}].url", "example.com 금지 — 수집 링크를 넣습니다", bag)
        take = a.get("takeaway") or ""
        if "하십시오" in take:
            err(p + ".takeaway", "시사점은 입니다/됩니다 톤. '하십시오' 금지", bag)
        for bad in VOICE_BAN:
            if bad in take or any(bad in (x or "") for x in (a.get("body") or [])):
                err(p, f"편집 메모 투 금지: {bad}", bag)
                break
        if len(take) < 60:
            err(p + ".takeaway", "시사점은 두 문장, 60자 이상", bag)
        if take.count("다.") + take.count("요.") < 1:
            err(p + ".takeaway", "종결 어미가 없습니다", bag)
        if a.get("id") not in ids:
            err(p + ".id", "should match a briefing id", bag)
        for para in a.get("body") or []:
            if isinstance(para, str) and len(para) < 80:
                err(p + ".body", "본문 한 단은 80자 이상", bag)
                break
    takes = [(a.get("takeaway") or "") for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    if takes and len(takes) != len(set(takes)):
        err("analysis.takeaway", "시사점 복붙 금지", bag)
    return bag


def normalize_headline(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"[\s\u200b-\u200f\u2028\u2029]+", "", s)
    return re.sub(r"[^\w가-힣]", "", s)


def url_core(u: str) -> str:
    try:
        p = urlparse(u.strip())
        host = (p.hostname or "").lower()
        path = (p.path or "").rstrip("/")
        return f"{host}{path}"
    except Exception:
        return u.strip().rstrip("/")


def check_quality(
    issue: dict,
    collected_urls: set[str] | None,
    prev: dict | None,
    date_str: str | None,
) -> tuple[list[str], list[str]]:
    """내용 품질 게이트. (errors, warnings) — warnings는 실패시키지 않는다."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. 발행일 일치 (수동 재실행·백필은 --date override)
    if date_str and issue.get("date") != date_str:
        errors.append(f"date: {issue.get('date')} != {date_str} (수동 재실행이면 --date로 지정)")

    # 2. 헤드라인 중복 (정규화 후 비교)
    heads: list[tuple[str, str]] = []
    for b in issue.get("briefing") or []:
        if isinstance(b, dict):
            heads.append(("briefing", normalize_headline(b.get("headline"))))
    for a in issue.get("analysis") or []:
        if isinstance(a, dict):
            heads.append(("analysis", normalize_headline(a.get("title"))))
    seen: dict[str, str] = {}
    for kind, h in heads:
        if not h:
            continue
        if h in seen:
            errors.append(f"headline-dup: {kind} 항목이 {seen[h]} 항목과 중복")
        else:
            seen[h] = kind

    # 3. 출력 URL ⊆ 수집 URL (환각 URL 방지)
    if collected_urls is not None:
        for i, a in enumerate(issue.get("analysis") or []):
            if not isinstance(a, dict):
                continue
            for s in a.get("sources") or []:
                u = str((s or {}).get("url") or "")
                if u and url_core(u) not in collected_urls:
                    errors.append(f"analysis[{i}].sources: 수집되지 않은 URL {u[:70]}")

    # 4. 전날 호 재탕 (warning — 이어지는 이슈도 있으므로)
    if prev:
        prev_heads: set[str] = set()
        for b in prev.get("briefing") or []:
            if isinstance(b, dict):
                prev_heads.add(normalize_headline(b.get("headline")))
        for a in prev.get("analysis") or []:
            if isinstance(a, dict):
                prev_heads.add(normalize_headline(a.get("title")))
        for kind, h in heads:
            if h and h in prev_heads:
                warnings.append(f"prev-dup: {kind} 헤드라인이 전날 호와 중복될 수 있음")
                break

    # 5. keynums 미검증 문구 잔류 (warning — 프론트에서 제외되지만 파이프라인도 경고)
    for k in issue.get("keynums") or []:
        sub = str((k or {}).get("sub") or "")
        if "교차검증 전" in sub or "초안" in sub:
            warnings.append("keynums: sub에 미검증 표시 잔류 (공개 지면에서는 제외됨)")
            break

    # 6. timeline t 포맷 (warning) — "MM/DD HH:MM" 권장, 구 형식 "MM-DD"도 허용
    for t in issue.get("timeline") or []:
        tt = str((t or {}).get("t") or "")
        if not tt:
            continue
        m = re.match(r"^(\d{2})[/-](\d{2})(?: (\d{2}):(\d{2}))?$", tt)
        ok = bool(m)
        if ok:
            mo, day = int(m.group(1)), int(m.group(2))
            ok = 1 <= mo <= 12 and 1 <= day <= 31
            if ok and m.group(3) is not None:
                ok = 0 <= int(m.group(3)) <= 23 and 0 <= int(m.group(4)) <= 59
        if not ok:
            warnings.append(f"timeline: t 포맷 비정상 '{tt}' (MM/DD HH:MM 기대)")
            break

    # 7. 목표 범위 초과 (warning)
    nb = len(issue.get("briefing") or [])
    if nb > 7:
        warnings.append(f"briefing: 목표 5~7 초과 ({nb}개)")
    for a in issue.get("analysis") or []:
        ex = str((a or {}).get("extra") or "")
        if len(ex) > 300:
            warnings.append(f"analysis extra: 300자 초과 ({len(ex)}자)")
            break

    # 8. 출처 URL은 경로가 있는 실제 기사여야 함 (generic 도메인 금지)
    for i, a in enumerate(issue.get("analysis") or []):
        if not isinstance(a, dict):
            continue
        for s in a.get("sources") or []:
            u = str((s or {}).get("url") or "").strip()
            if u and re.match(r"^https?://(www\.)?[a-zA-Z0-9-]+(\.[a-z]+)+/?(\?.*)?$", u):
                warnings.append(f"analysis[{i}].sources: generic URL '{u[:50]}' (경로 없는 도메인)")
                break

    # 9. body 최소 길이 + 금지 메타 문구
    BANNED_PHRASES = [
        "그날의 흐름을 잇기 위한 재구성입니다",
        "확인된 문장만 브리핑에 올렸고",
        "원문 링크와 공식 문서가 있으면 그쪽이 우선입니다",
    ]
    for i, a in enumerate(issue.get("analysis") or []):
        if not isinstance(a, dict):
            continue
        body = a.get("body", "")
        btext = " ".join(body) if isinstance(body, list) else str(body)
        if btext and len(btext) < 50:
            warnings.append(f"analysis[{i}].body: 50자 미만 ({len(btext)}자)")
        for bp in BANNED_PHRASES:
            if bp in btext:
                warnings.append(f"analysis[{i}].body: 금지 메타 문구 포함")
                break

    # 10. P0 출력 정리 게이트 (TPL/ID/DUP/VIA/RND)
    p0_err, p0_warn = check_p0(issue, prev)
    errors.extend(p0_err)
    warnings.extend(p0_warn)

    # 11. 2주차: 깊이 슬롯 게이트 + 근거 연결 + 문체 패스
    d_err, d_warn = check_depth(issue)
    errors.extend(d_err)
    warnings.extend(d_warn)

    return errors, warnings


# ---------------------------------------------------------------------------
# 2주차: 깊이 슬롯 게이트 (품질 개선 계획 v5)
# 슬롯 5개: 무슨 일인가 / 맥락 / 수치 2개+ / 한계·반론 / 왜 중요한가
# 생략: 기사별 ≤1개, 전체 생략 ≤ max(2, ceil(전체슬롯×0.10)). P1에서 비율→절대개수로 변경.
# 사유는 '근거 없음'으로 통일, 로그에 하위 사유.
# ---------------------------------------------------------------------------

DEPTH_SLOTS = ["what", "context", "numbers", "limits", "why"]
LIMIT_MARKERS = ["한계", "하지만", "단,", "주의", "반론", "다만", "아직", "불확실", "검증되지"]
WHY_MARKERS = ["중요", "의미", "영향", "바뀐", "달라진"]

# P1 (Codex): draft.py의 NUM_RE와 동일한 패턴 (AI 뉴스 영어 단위 포함).
# draft.py가 바뀌면 여기도 함께 바꿔야 한다.
NUM_RE_VALIDATE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|배|달러|억|만|점|분|시간|일|명|개)"
    r"|\$\d+(?:\.\d+)?\s*(?:B|M|K|billion|million)?(?![0-9A-Za-z])"
    r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:B|M|K)(?![0-9A-Za-z])"
    r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:million|billion|thousand|times)(?![0-9A-Za-z])"
    r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?x(?![0-9A-Za-z])",
    re.IGNORECASE,
)


def _slot_status(a: dict) -> dict[str, bool]:
    """단일 analysis의 슬롯 충족 여부."""
    bullets = a.get("bullets") or []
    body = a.get("body") or []
    takeaway = str(a.get("takeaway") or "")
    btext = " ".join(str(x) for x in (bullets if isinstance(bullets, list) else [bullets]))
    body_text = " ".join(str(x) for x in (body if isinstance(body, list) else [body]))
    full = btext + " " + body_text + " " + takeaway

    # what: body 첫 문단이 30자 이상
    first = str(body[0]) if isinstance(body, list) and body else ""
    what = len(first) >= 30
    # context: body 2개 문단 이상 (첫 문단=what, 둘째=맥락)
    context = isinstance(body, list) and len(body) >= 2 and len(str(body[1])) >= 30
    # numbers: 본문+bullet에 수치 2개 이상
    # P1 (Codex): draft.py의 NUM_RE와 동일한 패턴 사용
    nums = [m.group(0) for m in NUM_RE_VALIDATE.finditer(full)]
    numbers = len(nums) >= 2
    # limits: 한계·반론 마커 포함
    limits = any(m in full for m in LIMIT_MARKERS)
    # why: takeaway가 있고 왜-중요 마커 포함
    why = len(takeaway) >= 20 and any(m in full for m in WHY_MARKERS)
    return {"what": what, "context": context, "numbers": numbers, "limits": limits, "why": why}


def check_depth(issue: dict) -> tuple[list[str], list[str]]:
    """깊이 슬롯 + 근거 연결 + 문체 패스. (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    analyses = [a for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    if not analyses:
        return errors, warnings

    # 깊이 슬롯: 기사별 생략 ≤1개
    total_missing = 0
    for i, a in enumerate(analyses):
        status = _slot_status(a)
        missing = [s for s in DEPTH_SLOTS if not status[s]]
        total_missing += len(missing)
        if len(missing) > 1:
            errors.append(
                f"analysis[{i}].depth: 슬롯 {len(missing)}개 미충족 ({', '.join(missing)}) — 최대 1개까지 생략 가능"
            )
        elif len(missing) == 1:
            warnings.append(f"analysis[{i}].depth: 슬롯 1개 생략 ({missing[0]}) — 사유 '근거 없음' 기록 필요")

    # 전체 평균 생략률 ≤10% — P1 (Claude C-3): 소수 analysis의 이산화 문제 해소.
    # 비율이 아니라 절대 개수로: 허용 생략 = max(2, ceil(전체슬롯 × 0.10)).
    # 15슬롯이면 2개 허용 → 13.3% 통과. 대량 생략 방지 의도는 유지.
    total_slots = len(analyses) * len(DEPTH_SLOTS)
    allowed_missing = max(2, -(-total_slots // 10))  # ceil(total_slots * 0.10)
    avg_missing = total_missing / total_slots
    if total_missing > allowed_missing:
        errors.append(
            f"depth: 전체 슬롯 생략 {total_missing}개 > 허용 {allowed_missing}개 ({avg_missing:.0%})"
        )

    # 근거 연결: 출처 없는 수치 0건 — 수치 있는 문장에 출처 마커가 없으면 warning
    for i, a in enumerate(analyses):
        body = a.get("body") or []
        sources = a.get("sources") or []
        body_text = " ".join(str(x) for x in (body if isinstance(body, list) else [body]))
        nums = [m.group(0) for m in NUM_RE_VALIDATE.finditer(body_text)]
        if nums and not sources:
            warnings.append(f"analysis[{i}].evidence: 수치 {len(nums)}개 있으나 sources 없음")

    # 문체 패스: distinct-3 ≥ 0.869
    # 근거: 0주차 원본 실측 (fiv.co.kr 최근 3호 평균 0.919) − 5%p 허용 오차.
    # 상세: ~/workspace/fiv-panel/q_baseline_0week.md
    all_text = " ".join(
        str(b.get("headline") or "") + " " + str(b.get("summary") or "")
        for b in (issue.get("briefing") or []) if isinstance(b, dict)
    )
    for a in analyses:
        body = a.get("body") or []
        all_text += " " + " ".join(str(x) for x in (body if isinstance(body, list) else [body]))
    toks = all_text.split()
    grams = [tuple(toks[j:j+3]) for j in range(len(toks) - 2)]
    if grams:
        d3 = len(set(grams)) / len(grams)
        if d3 < 0.869:
            warnings.append(f"style: distinct-3 {d3:.3f} < 0.869 (반복 과다)")

    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--date", help="기대 발행일 (KST YYYY-MM-DD). 기본값: 오늘(KST)")
    ap.add_argument("--collected", type=Path, help="수집 스냅샷 JSON (URL ⊆ 검사)")
    ap.add_argument("--prev", type=Path, help="전날 호 JSON (재탕 검사)")
    args = ap.parse_args()
    date_str = args.date or datetime.now(KST).strftime("%Y-%m-%d")
    collected_urls: set[str] | None = None
    if args.collected and args.collected.exists():
        try:
            snap = json.loads(args.collected.read_text(encoding="utf-8"))
            collected_urls = {url_core(str(it.get("url") or "")) for it in snap.get("items", []) if it.get("url")}
        except Exception as e:
            print(f"WARN collected snapshot unreadable: {e}")
    prev: dict | None = None
    if args.prev and args.prev.exists():
        try:
            prev = json.loads(args.prev.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARN prev issue unreadable: {e}")
    failed = 0
    for f in args.files:
        issue = json.loads(f.read_text(encoding="utf-8"))
        bag = check(issue)
        qerr, qwarn = check_quality(issue, collected_urls, prev, date_str)
        bag.extend(qerr)
        if bag:
            failed += 1
            print(f"FAIL {f}")
            for line in bag:
                print("  -", line)
        else:
            nsrc = sum(len(a.get("sources") or []) for a in issue["analysis"])
            print(
                f"OK   {f.name} brief={len(issue['briefing'])} analysis={len(issue['analysis'])} "
                f"keynums={len(issue['keynums'])} tips={len(issue['tips'])} sources={nsrc}"
            )
        for line in qwarn:
            print(f"  ! WARN {f.name}: {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
