#!/usr/bin/env python3
"""P42 회귀 테스트: 요약 수리 fail-soft — 수리 실패가 attempt를 죽이지 않게.

배경 (실측, 2026-11-28호 attempt 2): briefing summary 8개 누락 → 수리
호출이 7개만 채움(7/8) → _repair_missing_summaries가 False → draft가
rc=4로 attempt 전체를 버렸다. 수리가 깨지거나 일부만 성공해도 나머지
분석·게이트 판정까지 갈 수 있어야 한다.

설계:
- 수리 부분 성공분은 근거 기반 LLM 값이라 유지한다. 남은 누락은 값을
  합성하지 않고 빈 값으로 normalize를 통과시킨다
  (normalize(allow_missing_summary=True), fail-soft 경로 전용).
- 판정은 validate가 맡는다: check()가 빈 summary를 "missing summary"
  hard 에러로 잡고(기존 불변조건의 집행 위치 확장 — 게이트 신설 아님),
  collect_structured_errors가 SCHEMA-001으로 남겨 다음 attempt
  피드백에 닿는다. 누락이 남은 한 발행 경로는 없다.
- 수리 실패 사실은 로그 + {date}.summary-repair.attempt{N}.json
  전용 sidecar에 남는다.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import draft
import validate
from draft import (
    SchemaError,
    _missing_summary_ids,
    _repair_missing_summaries,
    _write_summary_repair_sidecar,
    normalize,
    render_feedback,
)
from validate import check, collect_structured_errors, url_core

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _raw():
    return {
        "title": "테스트 호",
        "briefing": [
            {"id": "story-one", "headline": "첫 이야기",
             "summary": "첫 이야기의 요약으로 충분히 긴 문장입니다."},
            {"id": "story-two", "headline": "둘째 이야기"},
            {"id": "story-three", "headline": "셋째 이야기"},
        ],
        "analysis": [
            {"id": "story-one", "title": "첫 이야기 분석",
             "bullets": ["불릿 하나", "불릿 둘"],
             "body": ["본문 문단입니다. " * 10],
             "takeaway": "판단입니다. 다음 행동을 하면 됩니다.",
             "tags": ["테스트"], "sources": [{"url": "https://example.com/a"}]},
        ],
    }


SNAP = {"items": []}

# ---------- 1. 기본 경로는 불변: 누락이면 여전히 SchemaError ----------
try:
    normalize(_raw())
    ok("strict normalize는 여전히 SchemaError", False)
except SchemaError:
    ok("strict normalize는 여전히 SchemaError", True)

# ---------- 2. fail-soft normalize: 합성 없이 빈 값으로 통과 ----------
out = normalize(_raw(), allow_missing_summary=True)
sums = {b["id"]: b["summary"] for b in out["briefing"]}
ok("fail-soft: 있는 summary는 유지", sums["story-one"].startswith("첫 이야기"))
ok("fail-soft: 누락은 빈 값 (headline 복제 아님)",
   sums["story-two"] == "" and sums["story-three"] == "")

# ---------- 3. validate가 빈 summary를 hard로 판정 ----------
bag = check(out, None)
ok("validate check: 빈 summary 2건 hard 에러",
   sum(1 for x in bag if "missing summary" in x) == 2)
errs = collect_structured_errors(out, None)
schema = [e for e in errs if e.get("code") == "SCHEMA-001"]
ok("구조화 에러에 SCHEMA-001 2건", len(schema) == 2)
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "x.validate-errors.attempt2.json"
    p.write_text(json.dumps({"errors": errs}, ensure_ascii=False),
                 encoding="utf-8")
    fb = render_feedback(p)
ok("다음 attempt 피드백에 스키마 오류가 실린다",
   "스키마 오류" in fb and "summary 누락" in fb)

# ---------- 4. 수리 부분 성공 (11/28 attempt 2 양상): 1/2만 채워짐 ----------
raw = _raw()
def fake_chat(user):
    return json.dumps({"summaries": {
        "story-two": "수리로 채운 둘째 이야기 요약으로 충분히 긴 문장입니다."}})
res = _repair_missing_summaries(raw, SNAP, fake_chat)
ok("부분 성공이면 반환값은 False (전부 채워졌을 때만 True)", res is False)
ok("채워진 summary는 유지된다",
   raw["briefing"][1]["summary"].startswith("수리로 채운"))
ok("남은 누락만 정확히 남는다", _missing_summary_ids(raw) == ["story-three"])
# 부분 성공 뒤 fail-soft로 이어가면 validate가 남은 1건을 잡는다
out2 = normalize(raw, allow_missing_summary=True)
bag2 = check(out2, None)
ok("부분 수리 후 fail-soft → validate가 남은 1건만 hard 판정",
   sum(1 for x in bag2 if "missing summary" in x) == 1)

# ---------- 5. 수리 응답이 깨진 경우: issue 불변 + fail-soft 가능 ----------
raw = _raw()
res = _repair_missing_summaries(raw, SNAP, lambda user: "not json at all")
ok("깨진 수리 응답이면 False", res is False)
ok("깨진 수리는 issue를 건드리지 않는다",
   _missing_summary_ids(raw) == ["story-two", "story-three"])
out3 = normalize(raw, allow_missing_summary=True)
ok("수리 전면 실패 뒤에도 fail-soft로 validate까지 간다",
   sum(1 for x in check(out3, None) if "missing summary" in x) == 2)

# ---------- 6. fail-soft 기록 sidecar ----------
with tempfile.TemporaryDirectory() as td:
    pipe = Path(td)
    _write_summary_repair_sidecar(pipe, "2026-11-28", 2,
                                  ["story-two", "story-three"],
                                  ["story-three"])
    rep = json.loads((pipe / "2026-11-28.summary-repair.attempt2.json")
                     .read_text(encoding="utf-8"))
ok("sidecar: fixed/still_missing 기록",
   rep["fixed"] == ["story-two"] and rep["still_missing"] == ["story-three"])
ok("sidecar: validate sidecar와 파일명이 겹치지 않는다",
   not (pipe / "2026-11-28.validate-errors.attempt2.json").exists())

# ---------- 7. 기준선: 멀쩡한 픽스처에는 SCHEMA-001이 붙지 않는다 ----------
FIX = Path(__file__).resolve().parent / "fixtures"
ISSUE = json.loads((FIX / "2026-11-28-attempt3.issue.json")
                   .read_text(encoding="utf-8"))
SNAP38 = json.loads((FIX / "2026-11-28.collected.json")
                    .read_text(encoding="utf-8"))
_by = {}
for _it in SNAP38.get("items", []):
    if _it.get("url"):
        _by.setdefault(url_core(str(_it["url"])), _it)
_errs38 = collect_structured_errors(ISSUE, _by)
ok("P38 픽스처 구조화 에러 38건 유지 (SCHEMA-001 추가 없음)",
   len(_errs38) == 38
   and not any(e.get("code") == "SCHEMA-001" for e in _errs38))

print(f"test_p42: PASS {PASS} / FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
