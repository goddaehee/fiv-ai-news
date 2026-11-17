#!/usr/bin/env python3
"""P24 회귀 테스트: 2026-11-17호 run #99 — 게이트 오탐 + 피드백 공백.

실측 실패 원인:
1. NUMBERS-UNGROUNDED 오탐 "90일" — 입력 "90+30 disclosure policy"의
   구성 숫자는 뒤에 단위가 없어 NUM_RE·기존 입력 보강이 잡지 못했고,
   허용 집합은 ["30 days", "30"]뿐이었다. LLM이 "90일 유예 후 추가
   30일"로 정확히 풀어쓰자 attempt 1~3 전부 "90일"이 차단됐다.
   → 원문에 명시된 "A+B" 합성 표기에서만 구성 숫자를 분해해 허용
   집합에 넣는다. 단위는 합성 표기 뒤 단위·구성 숫자의 단위 동반
   등장에서 전파한다. 단위를 확정할 수 없으면 넣지 않는다.
2. KEYNUMS 피드백 공백 — KEYNUMS-SEMANTIC 에러 2건이
   collect_structured_errors에 없어 재시도에 전달되지 않았다.
   → keynums_semantic_findings로 판정을 구조화해 게이트와 피드백이
   공유하고, render_feedback에 사유별 처방을 추가한다.

진짜 환각은 여전히 차단돼야 한다: 합계(120일)·날조(45일)·단위 오용
(90%)·단위 없는 합성만으로 만든 "90일".
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import render_feedback
from validate import (
    _numbers_grounded_detail,
    check_keynums_semantics,
    collect_structured_errors,
    keynums_semantic_findings,
    url_core,
)

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _grounded(item, body):
    analysis = {"id": "x", "sources": [{"url": item["url"]}],
                "bullets": ["불릿"], "body": [body],
                "takeaway": "중요합니다. 대응이 필요합니다."}
    return _numbers_grounded_detail(analysis, {url_core(item["url"]): item})


# ---------- 1. (a) 합성 표기 분해 — run #99 실측 재현 ----------
pz = {"title": "Project Zero: 90+30 disclosure policy is changing",
      "url": "https://example.com/pz",
      "summary": "Google Project Zero is replacing its 90+30 disclosure "
                 "policy. Vendors had 30 days of grace after a patch."}
d = _grounded(pz, "기존 방식은 90일 유예 후 추가 30일을 주는 구조였습니다.")
ok("합성 분해: '90일 유예 후 추가 30일' 통과 (run #99 오탐 해소)", d["grounded"])
ok("합성 분해: 허용 표면에 '90+30' 포함", "90+30" in d["allowed_raw"])

# 합성 표기 바로 뒤에 단위가 붙은 경우
d = _grounded({"title": "New 90+30 days disclosure window",
               "url": "https://example.com/pz2",
               "summary": "The window shrinks."},
              "기존 방식은 90일 유예 후 추가 30일을 주는 구조였습니다.")
ok("합성 분해: '90+30 days' 뒤 단위 전파", d["grounded"])

# 한국어 합성 표기
d = _grounded({"title": "90+30일 공개 정책 교체",
               "url": "https://example.com/pz3",
               "summary": "기존 90+30일 정책을 더 짧은 기한으로 교체합니다."},
              "기존 방식은 90일 유예 후 추가 30일을 주는 구조였습니다.")
ok("합성 분해: 한국어 '90+30일' 분해", d["grounded"])

# EN↔KO 표면 쌍: percent 합성 → 한국어 % 출력
d = _grounded({"title": "SLA 99+1 percent credit",
               "url": "https://example.com/pz4",
               "summary": "The SLA offers a 99+1 percent credit structure."},
              "크레딧은 99%에서 시작해 1%가 더해집니다.")
ok("합성 분해: '99+1 percent' → '99%'·'1%' 통과", d["grounded"])

# ---------- 2. (a) 환각 차단은 약해지지 않는다 ----------
d = _grounded(pz, "기한은 총 120일로 늘어납니다.")
ok("환각 차단: 합계 '120일'은 여전히 차단",
   not d["grounded"] and any(b["raw"] == "120일" for b in d["bad"]))
d = _grounded(pz, "유예 기간은 45일입니다.")
ok("환각 차단: 날조 '45일'은 여전히 차단",
   not d["grounded"] and any(b["raw"] == "45일" for b in d["bad"]))
d = _grounded(pz, "비율은 90%입니다.")
ok("환각 차단: 단위 오용 '90%'는 여전히 차단",
   not d["grounded"] and any(b["raw"] == "90%" for b in d["bad"]))
d = _grounded({"title": "New 90+30 plan announced",
               "url": "https://example.com/pz5",
               "summary": "The company announced a 90+30 plan for subscribers."},
              "구독 기간은 90일 단위입니다.")
ok("환각 차단: 단위 없는 합성만으로는 '90일' 근거가 되지 않음",
   not d["grounded"] and any(b["raw"] == "90일" for b in d["bad"]))

# ---------- 3. (b) KEYNUMS-SEMANTIC findings ----------
bad_issue = {"keynums": [
    {"val": "3.2조 원", "lab": "Anthropic GNews", "sub": "수집 요약"},
    {"val": "미정", "lab": "example.com", "sub": "설명"},
    {"val": "47%", "lab": "분기 매출 비중", "sub": "본문 수치 기준"},
]}
findings = keynums_semantic_findings(bad_issue)
reasons = {(f["keynum_index"], f["reason"]) for f in findings}
ok("findings: 피드명 lab 검출", (0, "lab-feed-name") in reasons)
ok("findings: 내부 문자열 sub 검출", (0, "sub-internal") in reasons)
ok("findings: 숫자 없는 val 검출", (1, "val-no-number") in reasons)
ok("findings: 도메인뿐인 lab 검출", (1, "lab-domain-only") in reasons)
ok("findings: sub 내부 문자열(본문 수치) 검출", (2, "sub-internal") in reasons)
ok("findings: 정상 항목은 없음",
   all(f["keynum_index"] != 2 or f["reason"] == "sub-internal" for f in findings))

good_issue = {"keynums": [
    {"val": "47%", "lab": "분기 매출 비중", "sub": "실적 발표 기준"},
]}
ok("findings: 정상 keynums는 빈 목록", keynums_semantic_findings(good_issue) == [])

# 게이트 메시지 형식은 리팩터 전과 동일해야 한다 (기존 테스트·로그 호환)
bag: list[str] = []
check_keynums_semantics(bad_issue, bag)
ok("게이트: KEYNUMS-SEMANTIC 메시지 형식 유지",
   any("KEYNUMS-SEMANTIC: lab에 피드명·내부 문자열 포함 ('Anthropic GNews')" in e
       for e in bag)
   and any("KEYNUMS-SEMANTIC: val에 숫자가 없음 ('미정')" in e for e in bag)
   and any("KEYNUMS-SEMANTIC: sub에 내부 문자열 포함 ('수집 요약')" in e
           for e in bag))

# ---------- 4. (b) sidecar 수집 + 피드백 렌더링 ----------
issue = {"keynums": bad_issue["keynums"], "briefing": [], "analysis": []}
errs = collect_structured_errors(issue, None)
sem = [e for e in errs if e.get("code") == "KEYNUMS-SEMANTIC"]
ok("sidecar: KEYNUMS-SEMANTIC 수집됨", len(sem) >= 4)
ok("sidecar: keynum_index·reason 포함",
   any(e.get("keynum_index") == 0 and e.get("reason") == "lab-feed-name"
       for e in sem))

with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                 encoding="utf-8") as _f:
    json.dump({"errors": sem}, _f, ensure_ascii=False)
    _sidecar = _f.name
fb = render_feedback(_sidecar)
ok("피드백: KEYNUMS-SEMANTIC 처방 렌더링",
   "keynums[0]" in fb and "lab" in fb and "지표 이름" in fb)
ok("피드백: val 처방 렌더링", "keynums[1]" in fb and "숫자가 없습니다" in fb)

print(f"P24 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
