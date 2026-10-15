#!/usr/bin/env python3
"""파이프라인 재시도 로직 행동 테스트.

run.draft_with_retry()를 mock sh/sleep으로 실제 동작 검증한다.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "pipeline"))

import run


def _mock_issue(exists=True):
    m = MagicMock()
    m.exists.return_value = exists
    return m


def test_retry_succeeds_on_third_attempt():
    """2회 validate 실패 → 3회째 성공: rc=0, draft 3회 호출, --attempt 1/2/3, sleep 2회."""
    sh_calls = []
    sleep_calls = []
    validate_results = [1, 1, 0]  # 2회 실패 후 성공

    def fake_sh(cmd):
        sh_calls.append(cmd)
        return 0

    def fake_validate():
        return validate_results.pop(0)

    rc = run.draft_with_retry(
        ["draft.py", "--llm"],
        _mock_issue(exists=True),
        fake_validate,
        max_attempts=3,
        sh_fn=fake_sh,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    assert rc == 0, f"3회째 성공 시 rc=0이어야 함, got {rc}"
    assert len(sh_calls) == 3, f"draft 3회 호출, got {len(sh_calls)}"
    # --attempt 값이 1, 2, 3 순서인지
    attempts = [cmd[cmd.index("--attempt") + 1] for cmd in sh_calls]
    assert attempts == ["1", "2", "3"], f"attempt 1/2/3 순서, got {attempts}"
    assert sleep_calls == [10, 10], f"재시도 사이 2회 sleep, got {sleep_calls}"
    print("PASS: 2회 실패 → 3회째 성공")


def test_retry_all_fail():
    """3회 모두 validate 실패: rc!=0, sleep 2회 (마지막 뒤 sleep 없음)."""
    sleep_calls = []

    rc = run.draft_with_retry(
        ["draft.py"],
        _mock_issue(exists=True),
        lambda: 1,  # 항상 실패
        max_attempts=3,
        sh_fn=lambda cmd: 0,
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    assert rc != 0, "모두 실패 시 0이 아니어야 함"
    assert sleep_calls == [10, 10], "마지막 시도 뒤에는 sleep 없음"
    print("PASS: 3회 모두 실패 시 fail-closed")


def test_first_attempt_success_no_sleep():
    """첫 시도 성공 시 sleep 없이 즉시 반환."""
    sleep_calls = []
    sh_calls = []

    rc = run.draft_with_retry(
        ["draft.py"],
        _mock_issue(exists=True),
        lambda: 0,  # 첫 시도 성공
        max_attempts=3,
        sh_fn=lambda cmd: (sh_calls.append(cmd), 0)[1],
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    assert rc == 0
    assert len(sh_calls) == 1, "1회만 호출"
    assert sleep_calls == [], "성공 시 sleep 없음"
    print("PASS: 첫 시도 성공 시 즉시 반환")


def test_draft_failure_retries():
    """draft 자체 실패(rc!=0) 시에도 재시도."""
    sh_calls = []
    draft_results = [1, 1, 0]  # draft 2회 실패 후 성공

    def fake_sh(cmd):
        sh_calls.append(cmd)
        return draft_results.pop(0)

    rc = run.draft_with_retry(
        ["draft.py"],
        _mock_issue(exists=True),
        lambda: 0,
        max_attempts=3,
        sh_fn=fake_sh,
        sleep_fn=lambda s: None,
    )
    assert rc == 0
    assert len(sh_calls) == 3
    print("PASS: draft 실패 시 재시도")


def test_issue_not_created_retries():
    """issue 파일 미생성 시 재시도."""
    rc = run.draft_with_retry(
        ["draft.py"],
        _mock_issue(exists=False),  # 파일 없음
        lambda: 0,
        max_attempts=2,
        sh_fn=lambda cmd: 0,
        sleep_fn=lambda s: None,
    )
    assert rc != 0, "파일 미생성 시 실패"
    print("PASS: issue 미생성 시 재시도 후 실패")


def test_max_attempts_one_no_retry():
    """max_attempts=1이면 재시도 없음 (비-LLM 모드)."""
    sh_calls = []

    rc = run.draft_with_retry(
        ["draft.py"],
        _mock_issue(exists=True),
        lambda: 1,
        max_attempts=1,
        sh_fn=lambda cmd: (sh_calls.append(cmd), 0)[1],
        sleep_fn=lambda s: (_ for _ in ()).throw(AssertionError("sleep 호출되면 안 됨")),
    )
    assert rc != 0
    assert len(sh_calls) == 1
    print("PASS: max_attempts=1 시 재시도 없음")


if __name__ == "__main__":
    test_retry_succeeds_on_third_attempt()
    test_retry_all_fail()
    test_first_attempt_success_no_sleep()
    test_draft_failure_retries()
    test_issue_not_created_retries()
    test_max_attempts_one_no_retry()
    print("\n재시도 로직 행동 테스트 6개 통과")
