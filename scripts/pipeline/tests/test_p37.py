#!/usr/bin/env python3
"""P37 회귀 테스트: 실패 리포트 (6라운드 개선 6번).

배경: 발행 실패 시 워크플로우가 만드는 이슈 본문은 run URL + 아티팩트
이름뿐이라, 반복 장애를 집계할 재료(실패 단계·게이트·지연·복구)가 없었다.
워크플로우 파일은 권한 문제로 못 고치므로, 파이프라인(run.py)이
content/pipeline/<date>.failure-report.json/.md에 구조화해 남긴다.
이 테스트는 그 기록 로직(slot 판정·게이트 파싱·리포트 작성·복구 갱신·
attempt 로그)이 의도대로 동작하는지 검증한다.
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


KST = run.KST


def _dt(h, m):
    return datetime(2026, 11, 26, h, m, tzinfo=KST)


# --- slot_info: 소속 슬롯과 지연 -------------------------------------------
ok("05:30 정시 시작은 05:30 슬롯·지연 0",
   run.slot_info(_dt(5, 30)) == ("05:30", 0))
ok("05:47 시작은 05:30 슬롯·17분 지연",
   run.slot_info(_dt(5, 47)) == ("05:30", 17))
ok("07:59 시작도 05:30 슬롯 (다음 슬롯 전)",
   run.slot_info(_dt(7, 59)) == ("05:30", 149))
ok("08:30 시작은 재시도 슬롯·지연 0",
   run.slot_info(_dt(8, 30)) == ("08:30", 0))
ok("14:18 시작은 08:30 슬롯·348분 지연 (11/26 실측 패턴)",
   run.slot_info(_dt(14, 18)) == ("08:30", 348))
ok("새벽 03:00 시작은 manual·지연 없음",
   run.slot_info(_dt(3, 0)) == ("manual", None))

# --- parse_gate_codes: validate stdout에서 게이트 코드만 --------------------
_sample = """\
FAIL content/issues/2026-11-26.json
  - NUMBERS-UNGROUNDED analysis[1]: 본문 수치 '83달러'가 출처에 없음
  - TPL-001 analysis[0].takeaway/body: 템플릿 문구 '칸에 적으면'
  - SRC-ORPHAN-001 analysis[3].sources: 어느 문장과도 희귀 토큰이 겹치지 않음
  - NUMBERS-UNGROUNDED analysis[2]: 중복 코드는 한 번만
  ! WARN 2026-11-26.json: QUOTA-002 example.com: 출처 다변화 권장
  - 코드 없는 실패 문장은 게이트로 세지 않음
OK   2026-11-25.json brief=7 analysis=7 keynums=6 tips=1 sources=15
"""
_codes = run.parse_gate_codes(_sample)
ok("게이트 코드 3종 추출", _codes == ["NUMBERS-UNGROUNDED", "TPL-001", "SRC-ORPHAN-001"])
ok("WARN 줄의 코드는 실패 게이트로 세지 않음", "QUOTA-002" not in _codes)
ok("빈 출력은 빈 목록", run.parse_gate_codes("") == [])

# --- write_failure_report + mark_failure_recovered --------------------------
with tempfile.TemporaryDirectory() as td:
    pipe = Path(td)
    started = _dt(8, 30)
    attempts = [
        {"attempt": 1, "draft_rc": 0, "issue_created": True, "validate_rc": 1},
        {"attempt": 2, "draft_rc": 0, "issue_created": True, "validate_rc": 1},
        {"attempt": 3, "draft_rc": 5, "issue_created": True, "validate_rc": None},
    ]
    gates = {1: ["NUMBERS-UNGROUNDED"], 2: ["NUMBERS-UNGROUNDED", "TERM-001"]}
    jp = run.write_failure_report(
        pipe, "2026-11-26", started, "draft", 5,
        attempts=attempts, gates_by_attempt=gates,
        detail="LLM timeout (draft rc=5)")
    ok("리포트 JSON 생성", jp is not None and jp.exists())
    rep = json.loads(jp.read_text(encoding="utf-8"))
    ok("날짜·단계·종료 코드 기록",
       rep["date"] == "2026-11-26" and rep["stage"] == "draft" and rep["exit_code"] == 5)
    ok("슬롯·지연 기록", rep["schedule"]["started_slot"] == "08:30"
       and rep["schedule"]["start_delay_min"] == 0)
    ok("게이트 합집합 (시도별 합산·중복 제거)",
       rep["failed_gates"] == ["NUMBERS-UNGROUNDED", "TERM-001"])
    ok("시도별 게이트 부착", rep["attempts"][1]["failed_gates"] == ["NUMBERS-UNGROUNDED", "TERM-001"])
    ok("복구는 awaiting_retry로 시작", rep["recovery"]["status"] == "awaiting_retry")
    md = (pipe / "2026-11-26.failure-report.md").read_text(encoding="utf-8")
    ok("MD에 단계·게이트·복구 상태 포함",
       "draft" in md and "NUMBERS-UNGROUNDED" in md and "awaiting_retry" in md)

    # 복구 갱신: 14:18 발행 확정 → 05:30 슬롯 대비 528분 지연
    ok("복구 갱신 성공", run.mark_failure_recovered(pipe, "2026-11-26", _dt(14, 18)))
    rep2 = json.loads(jp.read_text(encoding="utf-8"))
    ok("복구 상태 recovered", rep2["recovery"]["status"] == "recovered")
    ok("발행 지연 528분 (05:30→14:18)", rep2["recovery"]["published_delay_min"] == 528)
    md2 = (pipe / "2026-11-26.failure-report.md").read_text(encoding="utf-8")
    ok("MD에도 복구 반영", "recovered" in md2 and "528" in md2)
    ok("리포트 없는 날짜 복구 갱신은 False",
       run.mark_failure_recovered(pipe, "2026-01-01", _dt(9, 0)) is False)

# --- fail-soft: 쓸 수 없는 경로에서도 예외 없이 None ------------------------
_blocker = Path(tempfile.mkdtemp()) / "afile"
_blocker.write_text("x", encoding="utf-8")
ok("리포트 작성 실패는 None (fail-soft)",
   run.write_failure_report(_blocker, "2026-11-26", _dt(5, 30), "collect", 3) is None)

# --- draft_with_retry attempt_log -------------------------------------------
_issue = MagicMock()
_issue.exists.return_value = True

# validate 2회 실패 후 성공: 시도 3건, validate_rc 1·1·0
_vres = [1, 1, 0]
_log: list = []
_rc = run.draft_with_retry(
    ["draft.py", "--llm"], _issue,
    lambda sidecar=None, attempt=None: _vres.pop(0),
    max_attempts=3, sh_fn=lambda cmd: 0, sleep_fn=lambda s: None,
    attempt_log=_log)
ok("성공 시 rc=0", _rc == 0)
ok("attempt_log 3건 누적", len(_log) == 3)
ok("attempt_log validate_rc 순서", [e["validate_rc"] for e in _log] == [1, 1, 0])
ok("attempt_log draft_rc는 0", all(e["draft_rc"] == 0 for e in _log))

# draft 타임아웃(rc=5): validate는 돌지 않고 validate_rc는 None
_log2: list = []
_rc2 = run.draft_with_retry(
    ["draft.py", "--llm"], _issue,
    lambda sidecar=None, attempt=None: 0,
    max_attempts=1, sh_fn=lambda cmd: 5, sleep_fn=lambda s: None,
    attempt_log=_log2)
ok("타임아웃 시 rc=5", _rc2 == 5)
ok("타임아웃 attempt는 validate_rc None",
   _log2 and _log2[0]["draft_rc"] == 5 and _log2[0]["validate_rc"] is None)

print(f"P37 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
