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
    rc = sh(draft_cmd)
    if issue.exists():
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
        v = sh(vcmd)
        if v != 0:
            return v
    return rc


if __name__ == "__main__":
    sys.exit(main())
