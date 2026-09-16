#!/usr/bin/env python3
"""Validate an issue JSON against the local schema (no extra deps)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URI_RE = re.compile(r"^https?://")
KINDS = {"hot", "talk", "rt", "doc"}


def err(path: str, msg: str, bag: list[str]) -> None:
    bag.append(f"{path}: {msg}")


def require(obj: dict, keys: list[str], path: str, bag: list[str]) -> None:
    for k in keys:
        if k not in obj:
            err(path, f"missing {k}", bag)


def check(issue: dict) -> list[str]:
    bag: list[str] = []
    require(
        issue,
        [
            "date",
            "title",
            "heroline",
            "dek",
            "tag",
            "briefMin",
            "readMin",
            "briefing",
            "keywords",
            "mainEvent",
            "keynums",
            "timeline",
            "intro",
            "analysis",
            "mood",
            "tips",
            "method",
        ],
        "$",
        bag,
    )
    if not DATE_RE.match(str(issue.get("date", ""))):
        err("date", "YYYY-MM-DD required", bag)
    if not (4 <= len(issue.get("briefing") or []) <= 14):
        err("briefing", "need 4–14 items", bag)
    if not (3 <= len(issue.get("keynums") or []) <= 16):
        err("keynums", "need 3–16 items", bag)
    if len(issue.get("timeline") or []) < 3:
        err("timeline", "need ≥3", bag)
    if not (2 <= len(issue.get("analysis") or []) <= 14):
        err("analysis", "need 2–14", bag)
    if len(issue.get("tips") or []) < 1:
        err("tips", "need ≥1", bag)
    mood = issue.get("mood") or {}
    for k in ("shift", "grow", "caution", "heat"):
        if not mood.get(k):
            err("mood", f"missing {k}", bag)

    ids = []
    for i, b in enumerate(issue.get("briefing") or []):
        require(b, ["id", "headline", "summary"], f"briefing[{i}]", bag)
        ids.append(b.get("id"))
    for i, a in enumerate(issue.get("analysis") or []):
        p = f"analysis[{i}]"
        require(a, ["id", "title", "bullets", "body", "takeaway", "tags", "sources"], p, bag)
        if len(a.get("bullets") or []) < 2:
            err(p + ".bullets", "need ≥2", bag)
        if len(a.get("body") or []) < 1:
            err(p + ".body", "need ≥1", bag)
        if len(a.get("sources") or []) < 1:
            err(p + ".sources", "need ≥1", bag)
        for j, s in enumerate(a.get("sources") or []):
            if s.get("kind") not in KINDS:
                err(f"{p}.sources[{j}].kind", "hot|talk|rt|doc", bag)
            if not URI_RE.match(str(s.get("url") or "")):
                err(f"{p}.sources[{j}].url", "http(s) url", bag)
        take = a.get("takeaway") or ""
        if "하십시오" in take:
            err(p + ".takeaway", "시사점은 입니다/됩니다 톤. '하십시오' 금지", bag)
        if a.get("id") not in ids:
            err(p + ".id", "should match a briefing id", bag)
    return bag


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    failed = 0
    for f in args.files:
        issue = json.loads(f.read_text(encoding="utf-8"))
        bag = check(issue)
        if bag:
            failed += 1
            print(f"FAIL {f}")
            for line in bag:
                print("  -", line)
        else:
            nsrc = sum(len(a.get("sources") or []) for a in issue["analysis"])
            print(
                f"OK   {f.name} brief={len(issue['briefing'])} analysis={len(issue['analysis'])} "
                f"keynums={len(issue['keynums'])} tips={len(issue['tips'])} sources={nsrc}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
