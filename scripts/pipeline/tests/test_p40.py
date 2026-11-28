"""P40 회귀 테스트: MUST-COVER 최종 attempt 출처 부착 (발행 실패 진단 건 3).

배경 (2026-11-28 attempt 3 실측): boston-scientific-breach 분석은
있었지만 sources가 0개여서 SOURCES-MISSING + MUST-COVER가 동시에 걸려
호 전체가 죽었다. attach_sources의 P18 빈 출처 복구는 본문-제목 토큰
겹침 ≥2가 조건인데, 한글 음차 본문은 영문 제목 토큰과 겹침이 0이라
닿지 않았다. P40은 최종 attempt에서만, cluster가 확정한 이야기 소속과
분석 id 토큰의 유일한 최강 일치를 근거로 그 이야기의 아이템을 붙인다.
게이트는 그대로 두고, 붙인 뒤에도 validate가 다시 판정한다.

픽스처는 test_p38과 같은 2026-11-28 attempt 3 실제 산출물이다.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from draft import _attach_must_cover_sources
from validate import collect_structured_errors, must_cover_findings, url_core

PASS = 0
FAIL = 0


def ok(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


FIX = Path(__file__).resolve().parent / "fixtures"
ISSUE = json.loads((FIX / "2026-11-28-attempt3.issue.json").read_text())
SNAP = json.loads((FIX / "2026-11-28.collected.json").read_text())
BY_URL = {}
for _it in SNAP["items"]:
    if _it.get("url"):
        BY_URL.setdefault(url_core(str(_it["url"])), _it)


def _codes(issue):
    return [e["code"] for e in collect_structured_errors(issue, BY_URL)]


# --- 기준선: MUST-COVER 1건(Boston), 분석은 있는데 출처 0개 -------------------
_base = copy.deepcopy(ISSUE)
_findings = must_cover_findings(_base, SNAP["items"])
ok("기준선 MUST-COVER 미충족 1건", len(_findings) == 1)
ok("미충족 이야기는 Boston Scientific",
   _findings and "Boston" in _findings[0]["title"])
_a3 = next(a for a in _base["analysis"] if a["id"] == "boston-scientific-breach")
ok("기준선: 해당 분석의 출처는 0개", not _a3.get("sources"))

# --- 부착: MUST-COVER와 SOURCES-MISSING이 함께 해소 --------------------------
_iss = copy.deepcopy(ISSUE)
_fixed = _attach_must_cover_sources(_iss, SNAP)
ok("부착된 분석은 boston-scientific-breach", _fixed == ["boston-scientific-breach"])
_a3 = next(a for a in _iss["analysis"] if a["id"] == "boston-scientific-breach")
ok("부착 후 출처 1개 이상", len(_a3.get("sources") or []) >= 1)
ok("부착 출처는 그 이야기의 아이템",
   all(url_core(s["url"]) in {url_core(u) for u in _findings[0]["urls"]}
       for s in _a3["sources"]))
ok("부착 후 MUST-COVER 0건", must_cover_findings(_iss, SNAP["items"]) == [])
_codes_after = _codes(_iss)
ok("부착 후 SOURCES-MISSING 해소", "SOURCES-MISSING" not in _codes_after)
ok("부착 후 MUST-COVER 구조화 에러 해소", "MUST-COVER" not in _codes_after)
# DEPTH(numbers·limits 슬롯 미충족)도 같은 분석 건이라 함께 해소된다 —
# 슬롯 판정이 인용 출처를 근거로 하기 때문이다. 대가는 SRC 경고 +2씩
# (한글 본문과 영문 제목의 토큰 겹침 0이라 붙는 경고로, 발행과 무관).
from collections import Counter
ok("부착 후 구성: hard 3건 해소, SRC 경고 +2씩",
   Counter(_codes_after) == Counter({"BODY-TOTAL": 6, "BODY-LENGTH": 1,
                                     "SRC-TOPIC": 16, "SRC-ORPHAN-001": 16}))

# --- 음성 1: 동점(모호)이면 건드리지 않는다 -----------------------------------
_amb = copy.deepcopy(ISSUE)
_dup = copy.deepcopy(_a3)
_dup["id"] = "boston-scientific-breach-copy"
_dup["sources"] = []
_amb["analysis"].append(_dup)
ok("동점 후보가 있으면 부착 안 함",
   _attach_must_cover_sources(_amb, SNAP) == [])
_a3amb = next(a for a in _amb["analysis"] if a["id"] == "boston-scientific-breach")
ok("동점 시 원본 분석 출처도 그대로 비어 있음", not _a3amb.get("sources"))

# --- 음성 2: 출처가 이미 있는 분석은 건드리지 않는다 --------------------------
_has = copy.deepcopy(ISSUE)
_a3h = next(a for a in _has["analysis"] if a["id"] == "boston-scientific-breach")
_a3h["sources"] = [{"site": "example", "title": "unrelated",
                    "url": "https://example.org/x"}]
ok("출처 있는 분석은 부착 대상 아님 (커버 판정과 무관)",
   _attach_must_cover_sources(_has, SNAP) == [])
ok("기존 출처 불변", _a3h["sources"][0]["url"] == "https://example.org/x")

# --- 음성 3: id 겹침이 약하면 건드리지 않는다 ---------------------------------
_weak = copy.deepcopy(ISSUE)
_a3w = next(a for a in _weak["analysis"] if a["id"] == "boston-scientific-breach")
_a3w["id"] = "unrelated-thing"
ok("id 토큰 겹침 <2면 부착 안 함",
   _attach_must_cover_sources(_weak, SNAP) == [])

# --- 배선: 최종 attempt에서만, 본문 수리보다 먼저 ------------------------------
_src = (Path(__file__).resolve().parent.parent / "draft.py").read_text()
_main = _src[_src.index("def main()"):]
ok("main에서 최종 attempt일 때만 호출",
   "if _final:" in _main and "_attach_must_cover_sources(issue, snap)" in _main)
ok("출처 부착이 본문 수리보다 먼저",
   _main.index("_attach_must_cover_sources(issue, snap)")
   < _main.index("_repair_short_bodies("))

print(f"P40 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
