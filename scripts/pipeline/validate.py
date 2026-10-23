#!/usr/bin/env python3
"""Validate an issue JSON against the local schema (no extra deps)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
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


_SENT1_FRAMES = [
    (re.compile(r"것이\s*이번\s*(.+?)\s*의\s*(?:의미|영향|시사점|가치|효과)\s*입니다"), "것이이번□의의미입니다"),
]
_SENT2_FRAMES = [
    (re.compile(r"[가-힣]+\s*보\s*면\s*됩?니다\s*$"), "□보면됩니다"),
]


def _takeaway_skeleton(tw: str) -> str:
    sents = [s.strip() for s in re.split(r"[.!?\n]+", tw) if s.strip()]
    if len(sents) < 2:
        return ""
    sk1 = next((tpl for pat, tpl in _SENT1_FRAMES if pat.search(sents[0])), "")
    if not sk1:
        return ""
    sk2 = next((tpl for pat, tpl in _SENT2_FRAMES if pat.search(sents[1])), "")
    if not sk2:
        return ""
    return sk1 + "‖" + sk2


def check_takeaway_template(issue: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    by_skel = {}
    for i, a in enumerate(issue.get("analysis") or []):
        if not isinstance(a, dict):
            continue
        tw = str(a.get("takeaway") or "").strip()
        if not tw:
            continue
        skel = _takeaway_skeleton(tw)
        if skel:
            by_skel.setdefault(skel, []).append(i)
    for skel, idxs in sorted(by_skel.items()):
        if len(idxs) >= 3:
            errors.append(f"TAKEAWAY-TPL: 시사점 {len(idxs)}개가 같은 뼈대({skel}) — 구조적 템플릿 반복 의심")
        elif len(idxs) == 2:
            warnings.append(f"TAKEAWAY-TPL: 시사점 2개가 같은 뼈대({skel}) — 템플릿 반복 주의")
    return errors, warnings


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

    # TAKEAWAY-TPL: 시사점 문장 뼈대(구조적 템플릿) 반복 방지 (Gemini안)
    tpl_err, tpl_warn = check_takeaway_template(issue)
    errors.extend(tpl_err)
    warnings.extend(tpl_warn)

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


# P12: keynums lab/sub에 들어가면 안 되는 내부 문자열·피드명 패턴.
# P10 폴백이 lab="Anthropic GNews", sub="수집 요약"인 깨진 항목을 발행한 사고의 재발 방지.
_KEYNUM_BAD_LAB = ("GNews", "수집 요약", "수집 항목", "Google News", "Hacker News")
_KEYNUM_BAD_SUB = ("수집 요약", "수집 항목", "수집 기준", "초안", "교차검증 전", "본문 수치")
_KEYNUM_DOMAIN_ONLY = re.compile(r"^[a-z0-9.-]+\.(com|net|org|io|ai|co|kr)$", re.IGNORECASE)


def check_keynums_semantics(issue: dict, bag: list[str]) -> None:
    """P12: keynums 의미 검증 — 개수만으로는 깨진 항목을 못 잡는다.

    각 항목은 (1) val에 실제 숫자가 들어 있고, (2) lab이 피드명·내부 문자열이
    아니며, (3) sub에 내부 문자열이 없어야 한다.
    val 단위까지 NUM_RE로 강제하지는 않는다 — 정상 발행본에 '125건', '2조 달러',
    '128GB'처럼 NUM_RE 밖 단위가 실제로 쓰이기 때문이다.
    """
    for i, k in enumerate(issue.get("keynums") or []):
        if not isinstance(k, dict):
            err(f"keynums[{i}]", "KEYNUMS-SEMANTIC: 항목이 객체가 아님", bag)
            continue
        val = str(k.get("val") or "").strip()
        lab = str(k.get("lab") or "").strip()
        sub = str(k.get("sub") or "").strip()
        if not val or not re.search(r"\d", val):
            err(f"keynums[{i}]", f"KEYNUMS-SEMANTIC: val에 숫자가 없음 ({val!r})", bag)
        if not lab:
            err(f"keynums[{i}]", "KEYNUMS-SEMANTIC: lab이 비어 있음", bag)
        else:
            if any(p in lab for p in _KEYNUM_BAD_LAB):
                err(f"keynums[{i}]", f"KEYNUMS-SEMANTIC: lab에 피드명·내부 문자열 포함 ({lab!r})", bag)
            if _KEYNUM_DOMAIN_ONLY.match(lab):
                err(f"keynums[{i}]", f"KEYNUMS-SEMANTIC: lab이 도메인뿐임 ({lab!r})", bag)
        if any(p in sub for p in _KEYNUM_BAD_SUB):
            err(f"keynums[{i}]", f"KEYNUMS-SEMANTIC: sub에 내부 문자열 포함 ({sub!r})", bag)


def check(issue: dict, collected_by_url: dict | None = None) -> list[str]:
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
    check_keynums_semantics(issue, bag)
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
    # 소스 쿼터: 단일 도메인이 analysis의 과반을 차지하면 발행 차단 (errors만)
    # P5: collected_by_url 전달 — origin_url 조인으로 불투명 Google News URL 해소
    # P6: 소스-주제 정합성에서 무관 판정된 소스는 분모에서 제외 (QUOTA 게이밍 방지)
    rel_exclude = _irrelevant_source_domains(issue, collected_by_url)
    quota_err, _ = check_source_quota(issue, collected_by_url, exclude=rel_exclude)
    bag.extend(quota_err)
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


def extract_domain(u: str) -> str:
    """URL에서 비교용 도메인 추출 (소문자, www. 제거). 실패 시 빈 문자열."""
    try:
        host = (urlparse(str(u or "")).hostname or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


QUOTA_ERR_RATIO = 0.50
QUOTA_WARN_RATIO = 0.25


def _source_domain(s, collected_by_url: dict | None) -> str:
    """source dict의 비교용 도메인. P5: origin_url(Google News <source url>) 우선,
    없으면 수집 스냅샷 조인으로 origin_url 탐색, 최후는 url 자체."""
    if not isinstance(s, dict):
        return extract_domain(s)
    ou = s.get("origin_url")
    if ou:
        return extract_domain(ou)
    if collected_by_url:
        it = collected_by_url.get(url_core(str(s.get("url") or "")))
        if it and it.get("origin_url"):
            return extract_domain(it["origin_url"])
    return extract_domain(s.get("url"))


def check_source_quota(issue: dict, collected_by_url: dict | None = None,
                        exclude: set | None = None) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    analyses = [a for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    if len(analyses) < 2:
        return errors, warnings
    counts = {}
    for i, a in enumerate(analyses):
        doms = set()
        for s in a.get("sources") or []:
            d = _source_domain(s, collected_by_url)
            # P6: 소스-주제 정합성에서 무관 판정된 소스는 분모에서 제외 (QUOTA 게이밍 방지)
            if d and (exclude is None or (i, d) not in exclude):
                doms.add(d)
        if not doms:
            warnings.append(f"analysis[{i}].sources: 추출 가능한 도메인 없음")
        for d in doms:
            counts[d] = counts.get(d, 0) + 1
    n = len(analyses)
    for d, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        share = c / n
        if share > QUOTA_ERR_RATIO:
            errors.append(f"QUOTA-001 {d}: 단일 도메인이 analysis {n}개 중 {c}개({share:.0%}) — 50% 초과 금지")
        elif share > QUOTA_WARN_RATIO and c >= 2:
            warnings.append(f"QUOTA-002 {d}: analysis {n}개 중 {c}개({share:.0%}) — 출처 다변화 권장")
    return errors, warnings


# ---------------------------------------------------------------------------
# P6: 소스-주제 정합성 게이트 (SRC-REL)
# 팩트 뉴스레터에서 주제와 무관한 출처가 붙는 것을 방지한다.
# 설계 원칙 (4자 패널 합의):
# - 오탐으로 정상 기사가 탈락하면 안 된다 → SRC-REL-001/101은 보류(holds),
#   자동 탈락이 아니라 수동 검토 대상. warnings로만 노출된다.
# - Grok의 우려 흡수: 게이트는 증상 완화용. 근본 치료(attach_sources
#   아키텍처 수정)는 별도 티켓.
# ---------------------------------------------------------------------------

_COMPANY_DOMAINS: dict[str, set[str]] = {
    "openai": {"openai.com"},
    "google": {"google.com", "blog.google", "deepmind.google"},
    "anthropic": {"anthropic.com"},
    "meta": {"meta.com", "facebook.com", "about.fb.com", "instagram.com"},
    "microsoft": {"microsoft.com", "azure.com"},
    "xai": {"x.ai"},
    "nvidia": {"nvidia.com", "blogs.nvidia.com"},
    "apple": {"apple.com"},
    "amazon": {"amazon.com", "aws.amazon.com"},
    "tesla": {"tesla.com"},
    "samsung": {"samsung.com"},
    "perplexity": {"perplexity.ai"},
    "cohere": {"cohere.com"},
    "mistral": {"mistral.ai"},
    "deepseek": {"deepseek.com"},
    "stability": {"stability.ai"},
    "midjourney": {"midjourney.com"},
    "huggingface": {"huggingface.co"},
}

_COMPANY_ALIASES: dict[str, list[str]] = {
    "openai": ["openai", "오픈ai", "chatgpt", "챗gpt"],
    "google": ["google", "구글", "gemini", "제미나이", "deepmind", "딥마인드"],
    "anthropic": ["anthropic", "앤스로픽", "claude", "클로드"],
    "meta": ["meta", "메타", "facebook", "페이스북", "llama", "라마"],
    "microsoft": ["microsoft", "마이크로소프트", "msft"],
    "xai": ["xai", "x.ai", "그록"],
    "nvidia": ["nvidia", "엔비디아"],
    "apple": ["apple", "애플"],
    "amazon": ["amazon", "아마존", "aws"],
    "tesla": ["tesla", "테슬라"],
    "samsung": ["samsung", "삼성"],
    "perplexity": ["perplexity", "퍼플렉시티"],
    "cohere": ["cohere", "코히어"],
    "mistral": ["mistral", "미스트랄"],
    "deepseek": ["deepseek", "딥시크"],
    "stability": ["stability ai", "스태빌리티"],
    "midjourney": ["midjourney", "미드저니"],
    "huggingface": ["huggingface", "허깅페이스"],
}

# 주제 무관하게 통과하는 중립 매체 (Gemini Tier 1 화이트리스트)
_NEUTRAL_MEDIA = {
    "techcrunch.com", "theverge.com", "arstechnica.com", "wired.com",
    "reuters.com", "bloomberg.com", "the-decoder.com", "venturebeat.com",
    "finance.yahoo.com", "forbes.com", "theguardian.com", "nytimes.com",
    "wsj.com", "ft.com", "bbc.com", "cnn.com", "theinformation.com",
    "axios.com", "politico.com", "simonwillison.net",
    "news.ycombinator.com", "reddit.com",
}

# 라벨이 명확한 사이트명인데 URL 도메인이 다르면 표기 오류 의심
_LABEL_DOMAINS = {
    "hacker news": "news.ycombinator.com",
    "github": "github.com",
    "reddit": "reddit.com",
    "arxiv": "arxiv.org",
    "youtube": "youtube.com",
    "wikipedia": "wikipedia.org",
}

# X3 면제: 종합/동향형 제목 키워드
_ROUNDUP_KEYWORDS = [
    "동향", "종합", "라운드업", "브리핑", "주간", "월간", "정리",
    "모음", "하이라이트", "결산", "다이제스트",
]


def _topic_companies(title: str) -> set[str] | None:
    """제목에서 식별된 회사 키 집합. 면제(X1/X2/X3)에 해당하면 None."""
    t = (title or "").lower()
    # X3: 종합/동향형 제목은 판정 스킵
    if any(k in t for k in _ROUNDUP_KEYWORDS):
        return None
    found: set[str] = set()
    for comp, aliases in _COMPANY_ALIASES.items():
        for al in aliases:
            if al in t:
                found.add(comp)
                break
    # X1: 회사명 0개, X2: 2개 이상(비교·파트너십 기사) → 스킵
    if len(found) != 1:
        return None
    return found


def _domain_owner(dom: str) -> str | None:
    """도메인의 소유 회사 키. 추적 대상이 아니면 None."""
    for comp, doms in _COMPANY_DOMAINS.items():
        for cd in doms:
            if dom == cd or dom.endswith("." + cd):
                return comp
    return None


def _relevance_classify(a: dict, collected_by_url: dict | None) -> dict:
    """analysis 한 개의 소스-주제 정합성 분류.
    반환: {"topic", "skipped", "sources": [(domain, cls, handle)], "flag"}.
    cls: topic | other | neutral | unknown."""
    entry: dict = {"topic": None, "skipped": True, "sources": [], "flag": None}
    topics = _topic_companies(str(a.get("title") or ""))
    if not topics:
        return entry
    topic = next(iter(topics))
    entry["topic"] = topic
    entry["skipped"] = False
    srcs: list[tuple[str, str, str]] = []
    for s in a.get("sources") or []:
        if not isinstance(s, dict):
            continue
        dom = _source_domain(s, collected_by_url)
        if not dom:
            continue
        owner = _domain_owner(dom)
        if owner == topic:
            cls = "topic"
        elif owner:
            cls = "other"
        elif dom in _NEUTRAL_MEDIA:
            cls = "neutral"
        else:
            cls = "unknown"
        srcs.append((dom, cls, str(s.get("handle") or "")))
    entry["sources"] = srcs
    if srcs:
        classes = {c for _, c, _ in srcs}
        # SRC-REL-001: 주제 회사 식별 + 전부 타 회사 도메인 + 중립 매체 없음
        if classes == {"other"}:
            entry["flag"] = "SRC-REL-001"
        # SRC-REL-002: 무관 회사 도메인이 중립 매체와 혼재 (주제 출처 없음)
        elif "other" in classes and "topic" not in classes and "neutral" in classes:
            entry["flag"] = "SRC-REL-002"
    return entry


def check_source_relevance(
    issue: dict, collected_by_url: dict | None = None
) -> tuple[list[str], list[str]]:
    """소스-주제 정합성 게이트. (holds, warnings)를 반환.
    holds(SRC-REL-001/101)는 자동 탈락이 아니라 수동 검토 대상 —
    호출자가 warnings로 노출한다."""
    holds: list[str] = []
    warnings: list[str] = []
    analyses = [a for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    for i, a in enumerate(analyses):
        # SRC-REL-101: 라벨이 명확한 사이트명인데 URL 도메인이 다름 (주제 식별 불필요)
        for s in a.get("sources") or []:
            if not isinstance(s, dict):
                continue
            h = str(s.get("handle") or "").strip().lower()
            if h in _LABEL_DOMAINS:
                dom = _source_domain(s, collected_by_url)
                exp = _LABEL_DOMAINS[h]
                if dom and dom != exp:
                    holds.append(
                        f"SRC-REL-101 analysis[{i}].sources: 라벨 '{s.get('handle')}'인데 "
                        f"URL 도메인은 {dom} (예상 {exp}) — 출처 표기 오류 의심, 수동 확인 필요"
                    )
                    break
        # 주제-출처 정합성 (면제 X1/X2/X3 적용)
        entry = _relevance_classify(a, collected_by_url)
        if entry["flag"] == "SRC-REL-001":
            doms = sorted({d for d, _, _ in entry["sources"]})
            holds.append(
                f"SRC-REL-001 analysis[{i}]: 주제 '{entry['topic']}'인데 출처가 전부 "
                f"타 회사 도메인({', '.join(doms)}) — 주제 무관 출처 의심, 수동 확인 필요"
            )
        elif entry["flag"] == "SRC-REL-002":
            others = sorted({d for d, c, _ in entry["sources"] if c == "other"})
            warnings.append(
                f"SRC-REL-002 analysis[{i}]: 주제 '{entry['topic']}'와 무관한 회사 도메인 "
                f"({', '.join(others)})이 중립 매체와 혼재 — 출처 적합성 확인 권장"
            )
    return holds, warnings


def _irrelevant_source_domains(
    issue: dict, collected_by_url: dict | None = None
) -> set[tuple[int, str]]:
    """소스-주제 정합성에서 무관 판정된 (analysis idx, domain) 집합.
    QUOTA 분모에서 제외해 무관 소스 갖다붙이기로 쿼터를 채우는 게이밍을 방지.
    조인 불가·면제·라벨 불일치(별도 문제)는 제외하지 않는다 (fail-closed)."""
    out: set[tuple[int, str]] = set()
    analyses = [a for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    for i, a in enumerate(analyses):
        entry = _relevance_classify(a, collected_by_url)
        if entry["skipped"]:
            continue
        for dom, cls, _h in entry["sources"]:
            if cls == "other":
                out.add((i, dom))
    return out


def check_quality(
    issue: dict,
    collected_urls: set[str] | None,
    prev: dict | None,
    date_str: str | None,
    collected_by_url: dict | None = None,
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
    d_err, d_warn = check_depth(issue, collected_by_url)
    errors.extend(d_err)
    warnings.extend(d_warn)

    # 12. P6: 소스-주제 정합성 (SRC-REL)
    # 보류(SRC-REL-001/101)는 자동 탈락이 아니라 수동 검토 대상 → warnings로 노출.
    # QUOTA 분모 제외는 check()에서 처리 (게이밍 동기 제거).
    rel_hold, rel_warn = check_source_relevance(issue, collected_by_url)
    warnings.extend(rel_hold)
    warnings.extend(rel_warn)

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

# P8: 정규식 단일 소스화 — draft.py의 NUM_RE를 직접 import.
# 수동 복사본 동기화 깨짐 방지.
# P10: normalize_num_text도 공유 (숫자-문자 사이 하이픈만 공백으로).
try:
    from draft import NUM_RE as NUM_RE_VALIDATE
    from draft import normalize_num_text as _normalize_num_text
except ImportError:
    # standalone 실행 시 fallback (draft.py와 동일한 패턴)
    NUM_RE_VALIDATE = re.compile(
        r"(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:%|배|달러|억|만|점|분|시간|일|명|개)"
        r"|\$\d+(?:\.\d+)?\s*(?:B|M|K|billion|million)?(?![0-9A-Za-z])"
        r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:B|M|K)(?![0-9A-Za-z])"
        r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?\s*(?:million|billion|thousand|times)(?![0-9A-Za-z])"
        r"|(?<![A-Za-z0-9\-])\d+(?:\.\d+)?x(?![0-9A-Za-z])",
        re.IGNORECASE,
    )

    def _normalize_num_text(text: str) -> str:
        return re.sub(r"(?<=\d)[-_](?=[A-Za-z])", " ", text or "")


# P10: 크기(magnitude) 단위 → 10의 거듭제곱 지수.
_MAG_UNIT = {
    "b": 9, "billion": 9, "billions": 9,
    "m": 6, "million": 6, "millions": 6,
    "k": 3, "thousand": 3, "thousands": 3,
    "억": 8, "만": 4, "천": 3,
}


def _canon_num(s: str) -> str:
    """수치 표면을 정규화하여 비교 가능하게 만듦.

    P10: 크기(magnitude) 기반 통일.
    - $80B / 80 billion / 800억 → 전부 "mag:80000000000"
    - 통화기호($·달러) 제거, 숫자 사이 콤마 제거
    - %, 배, 명, 개 등 크기 단위가 아닌 것은 기존처럼 표면 비교 유지
    - 80억($80B의 1/10)은 여전히 차단됨 (크기가 다름)

    P11 문서화 (Claude 권장): 통화는 grounding하지 않는다.
    - $·달러를 제거하고 크기만 비교하므로 "$80B"(달러)와 "800억"(원)이
      같은 크기로 통과한다. 달러↔원 단위 오기(예: $80B를 800억원으로 씀)는
      이 게이트가 잡지 못한다 — 통화를 검증하려면 별도 통화 게이트가 필요하다.
    """
    t = str(s or "").strip().lower()
    t = t.replace("$", "").replace("달러", "")
    t = re.sub(r",(?=\d)", "", t)  # 숫자 사이 콤마 제거 ("1,200" → "1200")
    t = re.sub(r"\s+", "", t)
    m = re.match(r"^(\d+(?:\.\d+)?)([a-z가-힣]*)$", t)
    if m:
        num, unit = m.group(1), m.group(2)
        if unit in _MAG_UNIT:
            try:
                val = Decimal(num) * (Decimal(10) ** _MAG_UNIT[unit])
                return f"mag:{int(val.to_integral_value())}"
            except InvalidOperation:
                pass
    # 크기 단위가 아니면 기존 동작: 영문 단위 약어화 + 소문자 + 공백 제거
    t = re.sub(r"\bbillions?\b", "b", t)
    t = re.sub(r"\bmillions?\b", "m", t)
    t = re.sub(r"\bthousands?\b", "k", t)
    return t


def _input_number_count(a: dict, collected_by_url: dict | None) -> int | None:
    """analysis 입력(summary)에 있던 검증기 통과 수치 후보 수.

    P2 (패널 만장일치): 입력에 숫자가 2개 미만이면 LLM이 numbers 슬롯을
    채울 수 없으므로, 조건부로 생략률 계산에서 제외(excused)한다.
    조인 불가(--collected 없음·URL 불일치)면 None → fail-closed(제외 안 함).
    """
    if not collected_by_url:
        return None
    cand: set[str] = set()
    matched = False
    for s in a.get("sources") or []:
        if not isinstance(s, dict):
            continue
        it = collected_by_url.get(url_core(str(s.get("url") or "")))
        if it is None:
            continue
        matched = True
        cand.update(m.group(0) for m in NUM_RE_VALIDATE.finditer(_normalize_num_text(it.get("summary") or "")))
    if not matched:
        return None
    return len(cand)


def _numbers_grounded_detail(a: dict, collected_by_url: dict | None) -> dict:
    """P9: 수치 근거 대조의 상세 진단 (feedback sidecar용).

    P7 (Claude Critical): 출력 수치가 입력 summary에 실제로 있는지 대조.
    P8: grounding 범위 확장 + 단위 정규화.
    P9: 진단용 상세 정보 반환 — 위반 위치(field)와 허용 수치 원문(raw).

    반환:
      {"grounded": bool, "joined": bool,
       "bad": [{"raw": str, "fields": [str]}],  # 입력에 없는 수치 + 검출 위치
       "allowed_raw": [str]}                    # 입력에서 확인된 수치 표면 (원문 그대로)
    조인 불가(collected_by_url=None·URL 불일치)면 grounded=True, joined=False → 검사 생략.
    """
    out: dict = {"grounded": True, "joined": False, "bad": [], "allowed_raw": []}
    if not collected_by_url:
        return out
    # 입력 title+summary들의 수치 집합 (P8: _canon_num 정규화)
    # P8: 하이픈을 공백으로 전처리한 뒤 매칭 (예: "120-billion" → "120 billion")
    input_nums: set[str] = set()
    allowed_raw: list[str] = []
    matched = False
    for s in a.get("sources") or []:
        if not isinstance(s, dict):
            continue
        it = collected_by_url.get(url_core(str(s.get("url") or "")))
        if it is None:
            continue
        matched = True
        # P8: title도 스캔 (payload에 title이 들어가므로)
        for text in (it.get("title") or "", it.get("summary") or ""):
            text = _normalize_num_text(text)
            for m in NUM_RE_VALIDATE.finditer(text):
                raw = m.group(0)
                norm = _canon_num(raw)
                if norm not in input_nums:
                    input_nums.add(norm)
                    allowed_raw.append(raw)
    if not matched:
        return out
    out["joined"] = True
    out["allowed_raw"] = allowed_raw
    # 출력 수치 추출 — 필드별 (위치 추적용). P8: extra 포함.
    def _field_text(field: str) -> str:
        v = a.get(field)
        if isinstance(v, list):
            return " ".join(str(x) for x in v)
        return str(v or "")
    bad_map: dict[str, dict] = {}
    for field in ("bullets", "body", "takeaway", "extra"):
        ftext = _normalize_num_text(_field_text(field))
        for m in NUM_RE_VALIDATE.finditer(ftext):
            raw = m.group(0)
            norm = _canon_num(raw)
            if norm not in input_nums:
                if norm not in bad_map:
                    bad_map[norm] = {"raw": raw, "fields": []}
                if field not in bad_map[norm]["fields"]:
                    bad_map[norm]["fields"].append(field)
    out["bad"] = list(bad_map.values())
    out["grounded"] = len(out["bad"]) == 0
    return out


def _numbers_grounded(a: dict, collected_by_url: dict | None) -> tuple[bool, list[str]]:
    """P9 이전 API 호환 래퍼. 반환: (grounded 여부, 입력에 없는 수치 목록)."""
    d = _numbers_grounded_detail(a, collected_by_url)
    return d["grounded"], [b["raw"] for b in d["bad"]]


def collect_structured_errors(issue: dict, collected_by_url: dict | None) -> list[dict]:
    """P9: 피드백 주입용 구조화 에러 리포트 (feedback sidecar 소스).

    반환 형식: [{code, analysis_index, analysis_id, fields, bad, allowed_raw, domains}]
    - bad: 차단된 수치 (피드백 렌더링 시에는 앵커 방지용으로 제외하고 allowed만 사용)
    P11: SOURCES-MISSING · NUMBERS-UNGROUNDED 외에 EMPTY-001 · TPL-001 ·
    TAKEAWAY-DUP · TAKEAWAY-TPL · QUOTA-001도 수집한다.
    """
    errors: list[dict] = []
    analyses = [a for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    # P10c: sources 누락 — 재시도 피드백용. LLM이 sources 키를 통째로 생략하는
    # 회귀(10/22: 3회 시도 전부 need ≥1 탈락)에 대응. hollow는 검증 실패이므로
    # 다음 시도에서 고치도록 피드백에 포함한다.
    for i, a in enumerate(analyses):
        srcs = [s for s in (a.get("sources") or [])
                if isinstance(s, dict) and str(s.get("url") or "").startswith("http")]
        if not srcs:
            errors.append({
                "code": "SOURCES-MISSING",
                "analysis_index": i,
                "analysis_id": a.get("id"),
            })
    for i, a in enumerate(analyses):
        status = _slot_status(a)
        if not status["numbers"]:
            continue
        d = _numbers_grounded_detail(a, collected_by_url)
        if not d["joined"] or d["grounded"]:
            continue
        fields = sorted({f for b in d["bad"] for f in b["fields"]})
        domains = sorted({
            extract_domain(str(s.get("url") or ""))
            for s in (a.get("sources") or [])
            if isinstance(s, dict) and s.get("url")
        })
        errors.append({
            "code": "NUMBERS-UNGROUNDED",
            "analysis_index": i,
            "analysis_id": a.get("id"),
            "fields": fields,
            "bad": [b["raw"] for b in d["bad"]],
            "allowed_raw": d["allowed_raw"],
            "domains": domains,
        })
    # P11 (Grok 권장): 피드백 커버리지 확대 — EMPTY-001 / TPL-001 /
    # TAKEAWAY-DUP / TAKEAWAY-TPL / QUOTA-001도 sidecar에 싣는다.
    # 판정은 기존 게이트(check_p0 / check_source_quota)를 그대로 재사용해
    # 게이트와 피드백이 어긋나지 않게 하고, 에러 문자열에서 코드·위치만 구조화한다.
    # 앵커 방지: TPL-001의 해당 문구는 sidecar에 싣지 않는다 (render_feedback도 인용 안 함).
    p0_errors, _ = check_p0(issue, None)
    for line in p0_errors:
        m = re.match(r"(EMPTY-001|TPL-001) analysis\[(\d+)\]\.", line)
        if m:
            idx = int(m.group(2))
            errors.append({
                "code": m.group(1),
                "analysis_index": idx,
                "analysis_id": analyses[idx].get("id") if idx < len(analyses) else None,
            })
        elif line.startswith(("TAKEAWAY-DUP", "TAKEAWAY-TPL")):
            errors.append({"code": line.split(":", 1)[0]})
    quota_errors, _ = check_source_quota(issue, collected_by_url)
    for line in quota_errors:
        m = re.match(r"QUOTA-001 (\S+):", line)
        if m:
            errors.append({"code": "QUOTA-001", "domain": m.group(1)})
    return errors


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


def check_depth(issue: dict, collected_by_url: dict | None = None) -> tuple[list[str], list[str]]:
    """깊이 슬롯 + 근거 연결 + 문체 패스. (errors, warnings).

    P2: numbers 슬롯이 missing이고 입력(summary)의 수치 후보가 2개 미만이면
    해당 슬롯을 생략률 계산에서 제외(excused)한다. 입력에 없는 걸 요구하지 않는다.
    조인 불가 시(collected_by_url=None·URL 불일치)는 기존 경로(fail-closed).
    """
    errors: list[str] = []
    warnings: list[str] = []

    analyses = [a for a in (issue.get("analysis") or []) if isinstance(a, dict)]
    if not analyses:
        return errors, warnings

    # 깊이 슬롯: 기사별 생략 ≤1개 (excused 제외 후 적용)
    total_missing = 0
    total_excused = 0
    for i, a in enumerate(analyses):
        status = _slot_status(a)
        missing = [s for s in DEPTH_SLOTS if not status[s]]
        # P2 조건부 제외: numbers 미충족 + 입력 수치 후보 2개 미만 → 제외
        if "numbers" in missing:
            n_cand = _input_number_count(a, collected_by_url)
            if n_cand is not None and n_cand < 2:
                missing.remove("numbers")
                total_excused += 1
                warnings.append(
                    f"analysis[{i}].depth: numbers 슬롯 제외 (입력 수치 후보 {n_cand}개 < 2)"
                )
        total_missing += len(missing)
        if len(missing) > 1:
            errors.append(
                f"analysis[{i}].depth: 슬롯 {len(missing)}개 미충족 ({', '.join(missing)}) — 최대 1개까지 생략 가능"
            )
        elif len(missing) == 1:
            warnings.append(f"analysis[{i}].depth: 슬롯 1개 생략 ({missing[0]}) — 사유 '근거 없음' 기록 필요")

    # 전체 평균 생략률 ≤10% — P1 (Claude C-3): 소수 analysis의 이산화 문제 해소.
    # P2: excused된 슬롯은 분모에서도 제외 (적용 가능한 슬롯만 카운트).
    # 비율이 아니라 절대 개수로: 허용 생략 = max(2, ceil(적용가능슬롯 × 0.10)).
    total_slots = len(analyses) * len(DEPTH_SLOTS) - total_excused
    allowed_missing = max(2, -(-total_slots // 10))  # ceil(total_slots * 0.10)
    avg_missing = total_missing / total_slots if total_slots else 0
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

    # P7 (Claude Critical): 수치 근거 대조 — 출력 수치가 입력 summary에 실제로 있는지 검사.
    # numbers 슬롯이 채워진 경우에만 검사 (비어 있으면 위 P2 excused 로직이 담당).
    # 입력에 없는 수치를 지어내면 NUMBERS-UNGROUNDED error로 발행 차단.
    for i, a in enumerate(analyses):
        status = _slot_status(a)
        if not status["numbers"]:
            continue
        grounded, bad = _numbers_grounded(a, collected_by_url)
        if not grounded:
            errors.append(
                f"analysis[{i}].numbers: 입력에 없는 수치 {len(bad)}개 검출 "
                f"({', '.join(bad[:5])}) — NUMBERS-UNGROUNDED"
            )

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
    ap.add_argument("--json-out", type=Path, help="P9: 구조화 에러 리포트를 JSON으로 저장 (피드백 sidecar)")
    args = ap.parse_args()
    date_str = args.date or datetime.now(KST).strftime("%Y-%m-%d")
    collected_urls: set[str] | None = None
    collected_by_url: dict[str, dict] | None = None
    if args.collected and args.collected.exists():
        try:
            snap = json.loads(args.collected.read_text(encoding="utf-8"))
            collected_by_url = {}
            for it in snap.get("items", []):
                if it.get("url"):
                    collected_by_url.setdefault(url_core(str(it.get("url"))), it)
            collected_urls = set(collected_by_url.keys())
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
        bag = check(issue, collected_by_url)
        qerr, qwarn = check_quality(issue, collected_urls, prev, date_str, collected_by_url)
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
        # P9: 피드백 sidecar — 구조화 에러 리포트 저장 (다음 attempt의 --feedback 소스)
        if args.json_out:
            try:
                rep = {
                    "file": str(f),
                    "date": issue.get("date"),
                    "failed": bool(bag),
                    "errors": collect_structured_errors(issue, collected_by_url),
                }
                args.json_out.parent.mkdir(parents=True, exist_ok=True)
                args.json_out.write_text(
                    json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            except Exception as e:
                print(f"WARN --json-out failed: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
