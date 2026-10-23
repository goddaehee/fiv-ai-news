#!/usr/bin/env python3
"""P13 회귀 테스트: 이미지 파이프라인 ↔ 발행 흐름 정합성.

배경 (실측):
- 10/16·10/23호: imggen이 이미지를 등록한 뒤 같은 날짜로 파이프라인을
  재실행하자 새 초안이 issue JSON을 덮어써 등록 이미지가 사라졌다.
  → draft.preserve_images로 id 일치 + 파일 실존 항목만 이관.
- 10/20·10/22호: 발행이 이미지 크론(당일만 처리)보다 늦어 영원히 누락.
  → images.py audit로 최근 N일 정합성 갭을 감지 가능하게.
"""

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import images as images_mod
from draft import preserve_images

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _issue(analyses):
    return {"date": "2026-10-23", "analysis": analyses}


def test_preserve_moves_matching_id():
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td) / "public"
        f = pub / "img" / "2026-10-23" / "a-1234abcd.webp"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
        entry = {"src": "/img/2026-10-23/a-1234abcd.webp", "caption": "c", "alt": "a",
                 "width": 1200, "height": 675}
        prev = _issue([{"id": "a", "images": [entry]}])
        new = _issue([{"id": "a"}, {"id": "b"}])
        moved = preserve_images(new, prev, pub)
        ok("id 일치+파일 실존 → 이관", moved == 1 and new["analysis"][0]["images"] == [entry])
        ok("이미지 없던 분석은 그대로", "images" not in new["analysis"][1])


def test_preserve_skips_changed_id():
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td) / "public"
        f = pub / "img" / "2026-10-23" / "old-1234abcd.webp"
        f.parent.mkdir(parents=True)
        f.write_bytes(b"x")
        prev = _issue([{"id": "old", "images": [{"src": "/img/2026-10-23/old-1234abcd.webp"}]}])
        new = _issue([{"id": "renamed"}])
        moved = preserve_images(new, prev, pub)
        ok("id 변경 시 이관 안 함", moved == 0 and "images" not in new["analysis"][0])


def test_preserve_drops_missing_file():
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td) / "public"
        pub.mkdir()
        prev = _issue([{"id": "a", "images": [{"src": "/img/2026-10-23/gone-1234abcd.webp"}]}])
        new = _issue([{"id": "a"}])
        moved = preserve_images(new, prev, pub)
        ok("파일 없는 참조는 이관 안 함", moved == 0 and "images" not in new["analysis"][0])


def test_preserve_noop_when_prev_empty():
    with tempfile.TemporaryDirectory() as td:
        pub = Path(td) / "public"
        pub.mkdir()
        prev = _issue([{"id": "a", "images": []}])
        new = _issue([{"id": "a"}])
        ok("이전 이미지가 없으면 0", preserve_images(new, prev, pub) == 0)


def _run_audit(root: Path, days: int = 7) -> dict:
    class Args:
        pass

    args = Args()
    args.days = days
    old = (images_mod.ROOT, images_mod.ISSUES, images_mod.IMGROOT)
    images_mod.ROOT = root
    images_mod.ISSUES = root / "content" / "issues"
    images_mod.IMGROOT = root / "public" / "img"
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = images_mod.cmd_audit(args)
        assert rc == 0
        return json.loads(buf.getvalue())
    finally:
        images_mod.ROOT, images_mod.ISSUES, images_mod.IMGROOT = old


def test_audit_detects_gaps():
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date().isoformat()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "content" / "issues").mkdir(parents=True)
        imgd = root / "public" / "img" / today
        imgd.mkdir(parents=True)
        (imgd / "ok-1111aaaa.webp").write_bytes(b"x")
        (imgd / "orphan-2222bbbb.webp").write_bytes(b"x")
        issue = {
            "date": today,
            "analysis": [
                {"id": "ok", "images": [{"src": f"/img/{today}/ok-1111aaaa.webp"}]},
                {"id": "none"},
                {"id": "broken", "images": [{"src": f"/img/{today}/gone-3333cccc.webp"}]},
            ],
        }
        (root / "content" / "issues" / f"{today}.json").write_text(
            json.dumps(issue), encoding="utf-8")
        rep = _run_audit(root)
        gap = rep["gaps"].get(today)
        ok("audit가 오늘 호 갭을 보고", gap is not None)
        if gap:
            ok("missing에 이미지 없는 분석", gap["missing"] == ["none"])
            ok("broken에 파일 없는 참조", gap["broken"] == [
                {"analysis": "broken", "src": f"/img/{today}/gone-3333cccc.webp"}])
            ok("orphans에 미참조 파일", gap["orphans"] == ["orphan-2222bbbb.webp"])


def test_audit_clean_issue_no_gap():
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date().isoformat()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "content" / "issues").mkdir(parents=True)
        imgd = root / "public" / "img" / today
        imgd.mkdir(parents=True)
        (imgd / "ok-1111aaaa.webp").write_bytes(b"x")
        issue = {"date": today,
                 "analysis": [{"id": "ok", "images": [{"src": f"/img/{today}/ok-1111aaaa.webp"}]}]}
        (root / "content" / "issues" / f"{today}.json").write_text(
            json.dumps(issue), encoding="utf-8")
        rep = _run_audit(root)
        ok("정상 호는 갭 없음", rep["gaps"] == {} and rep["checked"] == 1)


def main():
    test_preserve_moves_matching_id()
    test_preserve_skips_changed_id()
    test_preserve_drops_missing_file()
    test_preserve_noop_when_prev_empty()
    test_audit_detects_gaps()
    test_audit_clean_issue_no_gap()
    print(f"P13: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
