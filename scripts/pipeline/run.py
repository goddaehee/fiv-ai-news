#!/usr/bin/env python3
"""One-shot daily pipeline: collect → draft → validate.

Weekdays only by default (KST). Weekend files are not created.
"""

from __future__ import annotations

import argparse
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
    dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=KST)
    if dt.weekday() >= 5 and not args.allow_weekend:
        print(f"{date} is weekend — skip (use --allow-weekend to override)")
        return 0

    root = HERE.parents[1]
    pipe = root / "content" / "pipeline"
    pipe.mkdir(parents=True, exist_ok=True)
    collected = pipe / f"{date}.collected.json"
    issue = root / "content" / "issues" / f"{date}.json"

    if not args.skip_collect:
        rc = sh([sys.executable, str(HERE / "collect.py"), "--out", str(collected)])
        if rc != 0:
            return rc
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
        v = sh([sys.executable, str(HERE / "validate.py"), str(issue)])
        if v != 0:
            return v
    return rc


if __name__ == "__main__":
    sys.exit(main())
