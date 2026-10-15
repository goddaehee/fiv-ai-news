#!/usr/bin/env python3
"""One-shot daily pipeline: collect → draft → validate.

Runs every day including weekends (KST).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))


def sh(args: list[str]) -> int:
    print("+", " ".join(args))
    return subprocess.call(args)


def draft_with_retry(draft_cmd: list[str], issue, run_validate, max_attempts: int = 3,
                     sh_fn=None, sleep_fn=None) -> int:
    """draft → validate 재시도 루프. 테스트 가능성을 위해 sh/sleep 주입 가능."""
    import time
    _sh = sh_fn or sh
    _sleep = sleep_fn or time.sleep
    rc = 1
    for attempt in range(1, max_attempts + 1):
        cmd = list(draft_cmd) + ["--attempt", str(attempt)]
        print(f"[run] draft attempt {attempt}/{max_attempts}", file=sys.stderr)
        rc = _sh(cmd)
        if rc != 0:
            print(f"[run] draft failed (rc={rc}) on attempt {attempt}", file=sys.stderr)
        elif not issue.exists():
            print(f"[run] issue file not created on attempt {attempt}", file=sys.stderr)
            rc = 1
        else:
            v = run_validate()
            if v == 0:
                return 0
            print(f"[run] validate failed on attempt {attempt} — retrying", file=sys.stderr)
            rc = v
        if attempt < max_attempts:
            _sleep(10)
    print(f"[run] all {max_attempts} attempts failed — failing closed", file=sys.stderr)
    return rc


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
    date = args.date or now.strftime("%Y-%m-%d")

    root = HERE.parents[1]
    pipe = root / "content" / "pipeline"
    pipe.mkdir(parents=True, exist_ok=True)
    collected = pipe / f"{date}.collected.json"
    issue = root / "content" / "issues" / f"{date}.json"

    if not args.skip_collect:
        rc = sh([sys.executable, str(HERE / "collect.py"), "--out", str(collected)])
        if rc != 0:
            return rc
        # fail-closed: 수집 0건이면 조용히 넘기지 않고 실패
        try:
            snap = json.loads(collected.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"collected snapshot unreadable: {e}", file=sys.stderr)
            return 3
        if not snap.get("count"):
            print(
                f"collected 0 items (failed_feeds={snap.get('failed_feeds')}) — failing closed",
                file=sys.stderr,
            )
            return 3
    elif not collected.exists():
        print(f"missing {collected}", file=sys.stderr)
        return 2
    if args.collect_only:
        return 0

    draft_cmd = [sys.executable, str(HERE / "draft.py"), "--collected", str(collected), "--out", str(issue)]
    if args.llm:
        draft_cmd.append("--llm")
    if args.provider:
        draft_cmd.extend(["--provider", args.provider])

    def run_validate() -> int:
        vcmd = [
            sys.executable,
            str(HERE / "validate.py"),
            "--date",
            date,
            "--collected",
            str(collected),
            str(issue),
        ]
        prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_file = root / "content" / "issues" / f"{prev_date}.json"
        if prev_file.exists():
            vcmd.extend(["--prev", str(prev_file)])
        return sh(vcmd)

    # 재시도: 나쁜 LLM 샘플 한 번에 하루치가 날아가지 않게 최대 3회 시도.
    # 그래도 validate를 못 넘기면 fail-closed (AGENTS.md: 규칙 깨면 배포 안 함).
    max_attempts = 3 if args.llm else 1
    return draft_with_retry(draft_cmd, issue, run_validate, max_attempts)


if __name__ == "__main__":
    sys.exit(main())
