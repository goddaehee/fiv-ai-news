#!/usr/bin/env python3
"""P38 회귀 테스트: 최종 attempt 본문 길이 수리 (발행 실패 진단 건 1).

배경 (2026-11-26~28 이틀 연속 미발행 진단): 실패 9 attempt 중 8개가
BODY-TOTAL(본문 381~589자, 목표 600자)에서 걸렸다. 프롬프트 강화(PR #122)와
피드백 주입은 이미 있는데도 LLM이 문턱 근처에서 요동했고, P27 불릿 병합은
불릿이 명사형이면 소진된다 (11/28 attempt 3: 6개 분석이 526~579자).
게이트를 낮추지 않고, 최종 attempt에서만 길이 미달 분석을 골라 근거 기반
LLM 수리 1회(_repair_short_bodies)로 늘린다. 수리 결과는 결정적 가드
(길이 증가·문단 80자·완결 문장·신규 수치 금지)를 통과한 것만 채택된다.

픽스처: 2026-11-28 run 123 attempt 3의 실제 issue + 수집 스냅샷.
구조화 에러 38건이 원격 sidecar와 일치함을 진단에서 확인한 픽스처다
(tests/fixtures/2026-11-28-attempt3.issue.json / .collected.json).
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import _body_total, _para_complete, _repair_short_bodies
from validate import collect_structured_errors, url_core

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


FIX = Path(__file__).resolve().parent / "fixtures"
ISSUE = json.loads((FIX / "2026-11-28-attempt3.issue.json").read_text(encoding="utf-8"))
SNAP = json.loads((FIX / "2026-11-28.collected.json").read_text(encoding="utf-8"))


def _collected_by_url(snap):
    d = {}
    for it in snap.get("items", []):
        if it.get("url"):
            d.setdefault(url_core(str(it["url"])), it)
    return d


def _fresh_issue():
    return json.loads(json.dumps(ISSUE))


# --- 기준선: 픽스처가 원격 sidecar(38건)와 일치 ------------------------------
_errs = collect_structured_errors(_fresh_issue(), _collected_by_url(SNAP))
_cnt = Counter(e["code"] for e in _errs)
ok("픽스처 구조화 에러 38건 (원격 sidecar 일치)", len(_errs) == 38)
ok("기준선 코드 분포",
   _cnt == Counter({"SRC-TOPIC": 14, "SRC-ORPHAN-001": 14, "BODY-TOTAL": 6,
                    "SOURCES-MISSING": 1, "DEPTH": 1, "BODY-LENGTH": 1,
                    "MUST-COVER": 1}))


# --- 가짜 수리 LLM: 유능한 재작성을 흉내 (짧은 문단은 접고, 시사점+브리핑
# 요약으로 근거 문단을 덧붙인다 — 전부 픽스처 안에 있는 문장만 쓴다) ---------
def _fake_chat(issue):
    brief = {b["id"]: b for b in issue["briefing"]}

    def fake(user):
        req = json.loads(user)
        bodies = {}
        for r in req["analyses"]:
            a = next(x for x in issue["analysis"] if x["id"] == r["id"])
            paras: list[str] = []
            for p in a["body"]:
                if len(p) < 80 and paras:
                    paras[-1] += " " + p
                else:
                    paras.append(p)
            extra = (a["takeaway"] + " " + brief[a["id"]]["summary"]).strip()
            paras.append(extra)
            bodies[r["id"]] = paras
        return json.dumps({"bodies": bodies}, ensure_ascii=False)

    return fake


# --- 수리 본선: BODY-TOTAL 6건 → 0건 -----------------------------------------
_issue = _fresh_issue()
_fixed = _repair_short_bodies(_issue, SNAP, _fake_chat(_issue))
ok("수리 채택 6건", _fixed == 6)
ok("수리 후 전 분석 본문 600자 이상",
   all(_body_total(a) >= 600 for a in _issue["analysis"]))
_errs2 = collect_structured_errors(_issue, _collected_by_url(SNAP))
ok("수리 후 BODY-TOTAL 구조화 에러 0건",
   not [e for e in _errs2 if e["code"] == "BODY-TOTAL"])
# 짧은 문단을 접는 재작성이라 BODY-LENGTH 1건도 함께 사라진다 (실측 31건).
# 그 밖의 판정(SOURCES-MISSING·DEPTH·MUST-COVER·SRC 경고)은 그대로다.
ok("수리 후 총 31건 (BODY-TOTAL 6 + BODY-LENGTH 1 해소)",
   Counter(e["code"] for e in _errs2)
   == Counter({"SRC-TOPIC": 14, "SRC-ORPHAN-001": 14, "SOURCES-MISSING": 1,
               "DEPTH": 1, "MUST-COVER": 1}))

# --- 가드 1: 새 수치를 지어낸 수리는 거부 (11/26~28 반복된 '9.8점' 환각) -----
_issue = _fresh_issue()
_before = {a["id"]: list(a["body"]) for a in _issue["analysis"]}


def _hallucinating_chat(user):
    req = json.loads(user)
    bodies = {}
    for r in req["analyses"]:
        bodies[r["id"]] = [
            "이번 사건은 보안 점수 9.8점을 기록하며 업계의 주목을 받았습니다. "
            "수치가 보여주는 위험도는 기존 사례와 비교해도 높은 편에 속합니다. "
            "각 기관은 후속 공지를 통해 대응 방향을 밝히겠다고 전했습니다.",
            "이용자는 기관의 공식 안내를 확인하고, 출처가 불분명한 연락에는 "
            "응하지 않는 편이 안전합니다. 후속 보도가 이어지면 규모와 범위가 "
            "더 구체적으로 드러날 가능성이 있습니다. 관련 업계도 주시 중입니다.",
        ]
    return json.dumps({"bodies": bodies}, ensure_ascii=False)


_fixed = _repair_short_bodies(_issue, SNAP, _hallucinating_chat)
ok("환각 수치 수리는 전부 거부", _fixed == 0)
ok("거부 시 원본 본문 유지",
   all(a["body"] == _before[a["id"]] for a in _issue["analysis"]))

# --- 가드 2: 조각 문단(명사형 종결) 수리는 거부 -------------------------------
def _fragment_chat(user):
    req = json.loads(user)
    bodies = {}
    for r in req["analyses"]:
        bodies[r["id"]] = [
            "이번 유출은 단일 기관을 넘어 협력 업체 전반으로 번질 수 있는 사안입니다. "
            "기관은 조사에 착수했고, 결과가 나오면 공개하겠다고 밝혔습니다. "
            "이용자 안내도 함께 진행 중입니다.",
            "후속 조치와 업계 전반의 파장은 당분간 이어질 전망",
        ]
    return json.dumps({"bodies": bodies}, ensure_ascii=False)


_issue = _fresh_issue()
ok("조각 문단 수리는 거부", _repair_short_bodies(_issue, SNAP, _fragment_chat) == 0)

# --- 가드 3: 호출 실패·짧아진 수리는 조용히 원본 유지 -------------------------
def _boom_chat(user):
    raise TimeoutError("llm timeout")


_issue = _fresh_issue()
ok("수리 호출 실패 시 0건·예외 없음",
   _repair_short_bodies(_issue, SNAP, _boom_chat) == 0)
ok("실패 시 원본 본문 유지",
   all(a["body"] == _before[a["id"]] for a in _issue["analysis"]))


def _shrinking_chat(user):
    req = json.loads(user)
    return json.dumps(
        {"bodies": {r["id"]: ["짧은 요약 문장입니다. 확인됐습니다."] * 3
                    for r in req["analyses"]}},
        ensure_ascii=False)


_issue = _fresh_issue()
ok("짧아지는 수리는 거부", _repair_short_bodies(_issue, SNAP, _shrinking_chat) == 0)

# --- 배선: main()에서 최종 attempt일 때만 호출 --------------------------------
_src = (Path(__file__).resolve().parents[1] / "draft.py").read_text(encoding="utf-8")
ok("main()이 _final 조건으로 수리를 호출",
   "if _final:" in _src and "_repair_short_bodies(" in _src)
ok("수리 프롬프트에 신규 수치 금지 명시",
   "새 숫자를 만들지 않습니다" in _src)

print(f"P38 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
