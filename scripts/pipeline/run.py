#!/usr/bin/env python3
"""One-shot daily pipeline: collect → draft → validate.

Runs every day including weekends (KST).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))


def sh(args: list[str]) -> int:
    print("+", " ".join(args))
    return subprocess.call(args)


# ---------------------------------------------------------------------------
# P37 (6라운드 개선 6번): 실패 리포트.
# 실패 이슈는 워크플로우가 고정 본문(run URL + 아티팩트 이름)으로 만들어서,
# 반복 장애를 집계하려면 실패의 구조(단계·게이트·지연·복구)를 파이프라인이
# 직접 남겨야 한다. 워크플로우는 content/pipeline/을 통째로 아티팩트로
# 올리고 실패 이슈가 그 아티팩트를 가리키므로, 여기에 JSON+MD로 남긴다.
# 리포트 작성은 fail-soft — 어떤 경우에도 파이프라인 종료 코드를 바꾸지 않는다.

SLOTS_KST = [(5, 30), (8, 30)]  # daily-issue.yml cron: 05:30 1차, 08:30 재시도


def slot_info(started: datetime) -> tuple[str, int | None]:
    """실행 시작 시각의 소속 스케줄 슬롯과 예정 대비 지연(분).

    GitHub 스케줄 지연으로 늦게 뜬 실행은 가장 최근에 지난 슬롯 소속으로
    본다. 어느 슬롯보다 이른 새벽 시작은 수동 실행으로 보고 지연을 재지
    않는다 (None)."""
    mins = started.hour * 60 + started.minute
    slot = None
    for h, m in SLOTS_KST:
        if mins >= h * 60 + m:
            slot = (h, m)
    if slot is None:
        return "manual", None
    return f"{slot[0]:02d}:{slot[1]:02d}", mins - (slot[0] * 60 + slot[1])


_GATE_LINE_RE = re.compile(r"^([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\b")


def parse_gate_codes(text: str) -> list[str]:
    """validate stdout의 실패 줄("  - CODE ...")에서 게이트 코드만 뽑는다."""
    codes: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        m = _GATE_LINE_RE.match(s[2:])
        if m and m.group(1) not in codes:
            codes.append(m.group(1))
    return codes


def _failure_report_path(pipe_dir: Path, date: str) -> Path:
    return Path(pipe_dir) / f"{date}.failure-report.json"


def _render_failure_md(rep: dict) -> str:
    sch = rep.get("schedule") or {}
    rec = rep.get("recovery") or {}
    detail = f" ({rep['detail']})" if rep.get("detail") else ""
    delay = sch.get("start_delay_min")
    delay_txt = f"예정 대비 {delay}분 지연" if delay is not None else "수동 실행"
    rec_txt = rec.get("status") or ""
    if rec.get("status") == "recovered":
        rec_txt += (f" — {rec.get('recovered_at')} 발행 확정, "
                    f"05:30 슬롯 대비 {rec.get('published_delay_min')}분 지연")
    lines = [
        f"# 파이프라인 실패 리포트 {rep.get('date')}",
        "",
        f"- 실패 단계: {rep.get('stage')}{detail}",
        f"- 종료 코드: {rep.get('exit_code')}",
        f"- 시작: {rep.get('started_at')} (슬롯 {sch.get('started_slot')}, {delay_txt})",
        f"- 실패 확정: {rep.get('failed_at')} (실행 {rep.get('elapsed_min')}분)",
        f"- 실패 게이트: {', '.join(rep.get('failed_gates') or []) or '없음(게이트 외 실패)'}",
        f"- 경고·피드백 게이트: {', '.join(rep.get('warn_gates') or []) or '없음'}",
        f"- 복구: {rec_txt}",
        "",
        "## 시도별",
    ]
    for r in rep.get("attempts") or []:
        gates = ", ".join(r.get("failed_gates") or []) or "-"
        warn = ", ".join(r.get("warn_gates") or [])
        lines.append(
            f"- attempt {r.get('attempt')}: draft rc={r.get('draft_rc')}, "
            f"validate rc={r.get('validate_rc')}, 게이트: {gates}"
            + (f" (경고: {warn})" if warn else ""))
    return "\n".join(lines) + "\n"


def write_failure_report(pipe_dir, date: str, started_at: datetime, stage: str,
                         exit_code: int, attempts=None, gates_by_attempt=None,
                         detail: str | None = None) -> Path | None:
    """실패 구조를 <date>.failure-report.json/.md로 남긴다 (fail-soft)."""
    try:
        slot, delay_min = slot_info(started_at)
        now = datetime.now(KST)
        attempt_rows = []
        for row in attempts or []:
            r = dict(row)
            att = r.get("attempt")
            if gates_by_attempt and att in gates_by_attempt:
                # P39: hard/warn 분리 표기. dict({"hard","warn"})가 새 형식,
                # 구 형식(리스트)은 전부 hard로 본다.
                g = gates_by_attempt[att]
                if isinstance(g, dict):
                    r["failed_gates"] = list(g.get("hard") or [])
                    r["warn_gates"] = list(g.get("warn") or [])
                else:
                    r["failed_gates"] = list(g or [])
                    r["warn_gates"] = []
            attempt_rows.append(r)
        failed_gates: list[str] = []
        warn_gates: list[str] = []
        for r in attempt_rows:
            for g in r.get("failed_gates") or []:
                if g not in failed_gates:
                    failed_gates.append(g)
            for g in r.get("warn_gates") or []:
                if g not in warn_gates:
                    warn_gates.append(g)
        rep = {
            "date": date,
            "started_at": started_at.isoformat(timespec="seconds"),
            "failed_at": now.isoformat(timespec="seconds"),
            "stage": stage,
            "exit_code": exit_code,
            "detail": detail,
            "schedule": {
                "slots_kst": [f"{h:02d}:{m:02d}" for h, m in SLOTS_KST],
                "started_slot": slot,
                "start_delay_min": delay_min,
            },
            "elapsed_min": round((now - started_at).total_seconds() / 60, 1),
            "attempts": attempt_rows,
            "failed_gates": failed_gates,
            "warn_gates": warn_gates,
            "recovery": {
                "status": "awaiting_retry",
                "note": "같은 날 재시도 슬롯(08:30 KST) 등 후속 실행에서 "
                        "발행되면 recovered로 갱신된다",
                "recovered_at": None,
                "published_delay_min": None,
            },
        }
        pipe_dir = Path(pipe_dir)
        pipe_dir.mkdir(parents=True, exist_ok=True)
        jp = _failure_report_path(pipe_dir, date)
        jp.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
        (pipe_dir / f"{date}.failure-report.md").write_text(
            _render_failure_md(rep), encoding="utf-8")
        print(f"[run] failure report written: {jp}", file=sys.stderr)
        return jp
    except Exception as e:  # fail-soft: 리포트 실패가 본작업을 막지 않는다
        print(f"[run] failure report skipped: {e}", file=sys.stderr)
        return None


def mark_failure_recovered(pipe_dir, date: str, published_at: datetime) -> bool:
    """같은 날짜 실패 리포트가 있으면 복구 결과를 채운다 (fail-soft).

    GitHub Actions에서는 실행마다 새 체크아웃이라 이전 실행의 리포트가
    없을 수 있다 — 그 경우 아무것도 하지 않고 False를 돌려준다."""
    try:
        jp = _failure_report_path(pipe_dir, date)
        if not jp.exists():
            return False
        rep = json.loads(jp.read_text(encoding="utf-8"))
        first_slot = published_at.replace(hour=5, minute=30, second=0,
                                          microsecond=0)
        rep["recovery"] = {
            "status": "recovered",
            "note": "후속 실행에서 validate 통과·발행 확정됨",
            "recovered_at": published_at.isoformat(timespec="seconds"),
            "published_delay_min": round(
                (published_at - first_slot).total_seconds() / 60),
        }
        jp.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
        (Path(pipe_dir) / f"{date}.failure-report.md").write_text(
            _render_failure_md(rep), encoding="utf-8")
        print(f"[run] failure report marked recovered: {jp}", file=sys.stderr)
        return True
    except Exception as e:  # fail-soft
        print(f"[run] recovery mark skipped: {e}", file=sys.stderr)
        return False


def draft_with_retry(draft_cmd: list[str], issue, run_validate, max_attempts: int = 3,
                     sh_fn=None, sleep_fn=None, pipe_dir=None, date: str | None = None,
                     attempt_log: list | None = None) -> int:
    """draft → validate 재시도 루프. 테스트 가능성을 위해 sh/sleep 주입 가능.

    P9: 피드백 없는 재시도는 같은 환각을 반복한다 (10/19·10/20 연속 발행 실패).
    직전 attempt의 validate 에러 리포트를 sidecar 파일로 받아,
    다음 attempt의 draft 호출 시 --feedback으로 주입한다.
    P37: attempt_log를 주면 시도별 결과({attempt, draft_rc, issue_created,
    validate_rc})를 누적한다 — 실패 리포트(개선 6번)의 재료.
    """
    import time
    _sh = sh_fn or sh
    _sleep = sleep_fn or time.sleep
    rc = 1
    attempt = 0
    total = max_attempts
    bonus_used = False
    while attempt < total:
        attempt += 1
        cmd = list(draft_cmd) + ["--attempt", str(attempt)]
        # P9: 피드백 주입 — attempt 2부터 직전 시도 검증 리포트 전달.
        # P26: 직전 sidecar가 없으면(타임아웃으로 sidecar 미생성) 그 전
        # sidecar까지 거슬러 올라가 가장 최근 것을 쓴다 — 보너스 attempt도
        # 이전 검증 피드백을 받아야 하기 때문이다 (render_feedback이
        # 그보다 앞선 sidecar까지 합쳐 주므로 최신 1개만 넘기면 된다).
        if attempt > 1 and pipe_dir is not None and date:
            for _k in range(attempt - 1, 0, -1):
                prev_sidecar = Path(pipe_dir) / f"{date}.validate-errors.attempt{_k}.json"
                if prev_sidecar.exists():
                    cmd += ["--feedback", str(prev_sidecar)]
                    break
        print(f"[run] draft attempt {attempt}/{total}", file=sys.stderr)
        rc = _sh(cmd)
        entry = {"attempt": attempt, "draft_rc": rc,
                 "issue_created": bool(issue.exists()), "validate_rc": None}
        if rc != 0:
            print(f"[run] draft failed (rc={rc}) on attempt {attempt}", file=sys.stderr)
        elif not issue.exists():
            print(f"[run] issue file not created on attempt {attempt}", file=sys.stderr)
            rc = 1
        else:
            # P9: validate 에러 리포트를 sidecar로 저장 (다음 attempt의 --feedback 소스)
            sidecar = None
            if pipe_dir is not None and date:
                sidecar = Path(pipe_dir) / f"{date}.validate-errors.attempt{attempt}.json"
            # P23: 현재 attempt를 validate에 전달해 BODY-TOTAL 2단계 게이트가
            # 최종 전 attempt에서는 error, 최종 attempt에서는 완화 판정하게 한다.
            v = run_validate(sidecar, attempt)
            entry["validate_rc"] = v
            if v == 0:
                if attempt_log is not None:
                    attempt_log.append(entry)
                return 0
            print(f"[run] validate failed on attempt {attempt} — retrying", file=sys.stderr)
            rc = v
        if attempt_log is not None:
            attempt_log.append(entry)
        # P26: 마지막 attempt가 LLM 타임아웃(rc=5)으로 죽으면 스텝 제한
        # 30분 안에 여유가 있어(3 attempt ~10분) 1회 추가 시도한다.
        # 검증 실패(rc!=5)는 추가 시도를 받지 않는다 — 3회면 충분하다는
        # 기존 판단을 유지한다. 보너스 attempt는 --attempt 4로 돌며
        # validate는 attempt>=total이라 최종 attempt로 완화 판정한다.
        if rc == 5 and not bonus_used and attempt >= total:
            bonus_used = True
            total += 1
            print(f"[run] timeout on final attempt — bonus attempt {total}",
                  file=sys.stderr)
        if attempt < total:
            _sleep(10)
    print(f"[run] all {total} attempts failed — failing closed", file=sys.stderr)
    return rc


def finalize_publish(issue: Path) -> bool:
    """P19: 발행 확정 표시. validate 통과 = 발행이므로 draft:true를
    draft:false로 뒤집는다.

    지금까지는 어느 단계도 이 플래그를 뒤집지 않아, 발행된 호 전부가
    draft:true인 채로 라이브에 서빙됐다 (4차 패널 평가 지적). draft 키가
    없는 호(손편집·발행 확정)는 손대지 않는다 — published_lock의 잠금
    의미(키 없음 = 잠금)를 finalize가 깨면 안 된다."""
    try:
        data = json.loads(issue.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[run] finalize skipped (unreadable issue): {e}", file=sys.stderr)
        return False
    if data.get("draft") is not True:
        return False
    data["draft"] = False
    issue.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"[run] finalized publish: {issue.name} draft -> false")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--provider", choices=["xai", "glm", "openai"])
    ap.add_argument("--allow-weekend", action="store_true")
    ap.add_argument("--collect-only", action="store_true")
    ap.add_argument("--skip-collect", action="store_true")
    args = ap.parse_args()

    now = datetime.now(KST)
    started_at = now  # P37: 실패 리포트의 시작 시각·지연 계산 기준
    date = args.date or now.strftime("%Y-%m-%d")

    root = HERE.parents[1]
    pipe = root / "content" / "pipeline"
    pipe.mkdir(parents=True, exist_ok=True)
    collected = pipe / f"{date}.collected.json"
    issue = root / "content" / "issues" / f"{date}.json"

    if not args.skip_collect:
        rc = sh([sys.executable, str(HERE / "collect.py"), "--out", str(collected)])
        if rc != 0:
            write_failure_report(pipe, date, started_at, "collect", rc,
                                 detail=f"collect.py rc={rc}")
            return rc
        # fail-closed: 수집 0건이면 조용히 넘기지 않고 실패
        try:
            snap = json.loads(collected.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"collected snapshot unreadable: {e}", file=sys.stderr)
            write_failure_report(pipe, date, started_at, "collect", 3,
                                 detail="collected snapshot unreadable")
            return 3
        if not snap.get("count"):
            print(
                f"collected 0 items (failed_feeds={snap.get('failed_feeds')}) — failing closed",
                file=sys.stderr,
            )
            write_failure_report(pipe, date, started_at, "collect", 3,
                                 detail="collected 0 items")
            return 3
    elif not collected.exists():
        print(f"missing {collected}", file=sys.stderr)
        write_failure_report(pipe, date, started_at, "collect", 2,
                             detail="collected snapshot missing (--skip-collect)")
        return 2
    if args.collect_only:
        return 0

    draft_cmd = [sys.executable, str(HERE / "draft.py"), "--collected", str(collected), "--out", str(issue)]
    if args.llm:
        draft_cmd.append("--llm")
    if args.provider:
        draft_cmd.extend(["--provider", args.provider])

    # P37: attempt별 실패 게이트 수집 (실패 리포트용). validate stdout의
    # 게이트 코드 + sidecar 구조화 코드를 합집합으로 모은다.
    # P39: hard(발행 차단)와 warn(경고·피드백)을 나눠 모은다 — stdout의
    # 실패 줄은 hard, sidecar 코드는 validate가 실은 severity로 가른다.
    validate_gates: dict[int, dict] = {}

    def run_validate(json_out: Path | None = None, attempt: int | None = None) -> int:
        vcmd = [
            sys.executable,
            str(HERE / "validate.py"),
            "--date",
            date,
            "--collected",
            str(collected),
            str(issue),
        ]
        if attempt is not None:
            vcmd.extend(["--attempt", str(attempt), "--attempts-total", str(max_attempts)])
        if json_out is not None:
            vcmd.extend(["--json-out", str(json_out)])
        prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_file = root / "content" / "issues" / f"{prev_date}.json"
        if prev_file.exists():
            vcmd.extend(["--prev", str(prev_file)])
        # P37: 출력을 캡처해 그대로 흘려보내고(로그 보존), 게이트 코드를
        # 뽑아 실패 리포트에 싣는다.
        print("+", " ".join(vcmd))
        proc = subprocess.run(vcmd, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if attempt is not None:
            hard = parse_gate_codes(proc.stdout or "")
            warn: list[str] = []
            if json_out is not None and Path(json_out).exists():
                try:
                    rep = json.loads(Path(json_out).read_text(encoding="utf-8"))
                    for e in rep.get("errors") or []:
                        c = e.get("code")
                        if not c:
                            continue
                        # P39: severity가 없는 구 sidecar는 hard로 본다.
                        if e.get("severity") == "warn":
                            if c not in warn and c not in hard:
                                warn.append(c)
                        elif c not in hard:
                            hard.append(c)
                except Exception:
                    pass
            validate_gates[attempt] = {"hard": hard, "warn": warn}
        return proc.returncode

    # 재시도: 나쁜 LLM 샘플 한 번에 하루치가 날아가지 않게 최대 3회 시도.
    # 그래도 validate를 못 넘기면 fail-closed (AGENTS.md: 규칙 깨면 배포 안 함).
    # P9: sidecar 피드백 주입 (pipe_dir/date 전달 → attempt 2+에 --feedback).
    max_attempts = 3 if args.llm else 1
    # P27: draft에도 총 시도 횟수를 넘겨 최종 attempt에서 불릿 병합
    # 결정적 확장을 적용하게 한다 (validate의 --attempts-total과 같은 값).
    draft_cmd.extend(["--attempts-total", str(max_attempts)])
    attempt_log: list = []
    rc = draft_with_retry(draft_cmd, issue, run_validate, max_attempts,
                          pipe_dir=pipe, date=date, attempt_log=attempt_log)
    if rc == 0:
        # P19: validate 통과 = 발행 확정. 워크플로우 커밋 전에 draft를
        # false로 뒤집어, 발행본이 draft:true로 나가지 않게 한다.
        finalize_publish(issue)
        # P37: 같은 날짜 실패 리포트가 있으면 복구 결과를 채운다.
        mark_failure_recovered(pipe, date, datetime.now(KST))
    else:
        # P37: 실패 단계 판정 — 마지막 attempt에서 validate가 돌았으면
        # validate, draft 자체가 죽었으면 draft (rc로 종류를 덧붙인다).
        stage, detail = "draft", None
        if attempt_log:
            last = attempt_log[-1]
            if last.get("validate_rc") not in (None, 0):
                stage = "validate"
            elif last.get("draft_rc") == 5:
                detail = "LLM timeout (draft rc=5)"
            elif last.get("draft_rc") == 4:
                detail = "schema/JSON error (draft rc=4)"
            elif last.get("draft_rc"):
                detail = f"draft rc={last['draft_rc']}"
            elif not last.get("issue_created"):
                detail = "issue file not created"
        write_failure_report(pipe, date, started_at, stage, rc,
                             attempts=attempt_log,
                             gates_by_attempt=validate_gates,
                             detail=detail)
    return rc


if __name__ == "__main__":
    sys.exit(main())
