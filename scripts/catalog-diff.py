#!/usr/bin/env python3
"""레포 카탈로그 패리티 검사 — 우리 카탈로그 vs fiv.co.kr 원본.

사용법: python3 scripts/catalog-diff.py [--json content/repos-catalog.json]
원본 https://fiv.co.kr/repos 에서 딥다이브 슬러그 목록을 가져와 비교합니다.
종료 코드 0 = 패리티 유지, 1 = 차이 발견.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ORIG_URL = "https://fiv.co.kr/repos"
HREF_RE = re.compile(r'href="([a-zA-Z0-9_./-]*)-deep-dive\.html"')


def fetch_orig_html() -> str:
    import http.client
    import shutil
    import subprocess

    # 1) curl 우선 (서버가 urllib 연결을 중간에 끊는 경우가 있음)
    if shutil.which("curl"):
        try:
            out = subprocess.run(
                ["curl", "-sL", "--max-time", "30", "-A", "fiv-ai-news-catalog-diff/1.0", ORIG_URL],
                capture_output=True, timeout=40,
            )
            if out.returncode == 0 and len(out.stdout) > 10000:
                return out.stdout.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
    # 2) urllib 폴백
    req = urllib.request.Request(ORIG_URL, headers={"User-Agent": "fiv-ai-news-catalog-diff/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except http.client.IncompleteRead as e:
        raw = e.partial
    return raw.decode("utf-8", "replace")


def orig_slugs() -> set[str]:
    html = fetch_orig_html()
    slugs = {m.group(1).lower() for m in HREF_RE.finditer(html)}
    if len(slugs) < 100:
        raise RuntimeError(f"원본 파싱 결과 {len(slugs)}개 — 페이지가 비정상적입니다")
    return slugs


def our_slugs(path: Path) -> set[str]:
    cat = json.loads(path.read_text(encoding="utf-8"))
    out = set()
    for c in cat:
        for s in c.get("subs", []):
            for it in s.get("items", []):
                out.add(str(it["slug"]).lower())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="content/repos-catalog.json")
    args = ap.parse_args()
    try:
        orig = orig_slugs()
    except Exception as e:  # noqa: BLE001
        print(f"원본 조회 실패: {e}", file=sys.stderr)
        return 2
    ours = our_slugs(Path(args.json))
    missing = sorted(orig - ours)  # 원본에만 있음 → 우리가 추가해야 할 것
    extra = sorted(ours - orig)  # 우리에게만 있음
    print(f"원본: {len(orig)} / 우리: {len(ours)}")
    if missing:
        print(f"\n원본에만 ({len(missing)}):")
        for s in missing:
            print(f"  - {s}")
    if extra:
        print(f"\n우리에게만 ({len(extra)}):")
        for s in extra:
            print(f"  + {s}")
    if not missing and not extra:
        print("패리티 유지 — 차이 없음")
        return 0
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
