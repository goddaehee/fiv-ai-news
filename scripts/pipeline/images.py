#!/usr/bin/env python3
"""Image pipeline for fiv-ai-news (#3).

Contract (panel consensus 2026-10-14):
- AI-generated abstract illustrations only. Never use original or third-party images.
- One image max per analysis, only when it adds value (0..1).
- Caption: "AI 생성 일러스트 (실제 사진 아님)".
- Idempotent: file <analysis-id>-<prompthash8>.webp in public/img/<date>/.
  Skip when the file already exists and the prompt hash matches.
- WebP, max width 1200px, quality ~80.

Generation itself needs an image model. This script handles the deterministic
parts: planning (which analyses lack images), file naming, format conversion,
resizing, and registering results into the issue JSON. Prompt refinement
(strip proper nouns -> abstract concept) and image generation are done by the
calling agent (see runbook in docs or the daily cron).

Usage:
  python3 scripts/pipeline/images.py --plan --date 2026-10-14
      -> prints JSON list of analyses needing images
  python3 scripts/pipeline/images.py --register --date 2026-10-14 \\
      --analysis <analysis-id> --src <generated.png> \\
      --prompt "..." --model "..." --alt "..."
      -> converts to WebP, saves under public/img/<date>/, updates issue JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISSUES = ROOT / "content" / "issues"
IMGROOT = ROOT / "public" / "img"

CAPTION = "AI 생성 일러스트 (실제 사진 아님)"
MAX_WIDTH = 1200
WEBP_QUALITY = 80


def prompthash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]


def img_name(analysis_id: str, prompt: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in analysis_id)[:40]
    return f"{safe}-{prompthash(prompt)}.webp"


def load_issue(date: str) -> tuple[Path, dict]:
    p = ISSUES / f"{date}.json"
    if not p.exists():
        print(f"no issue file: {p}", file=sys.stderr)
        sys.exit(1)
    return p, json.loads(p.read_text(encoding="utf-8"))


def cmd_plan(date: str) -> int:
    _, issue = load_issue(date)
    out = []
    for a in issue.get("analysis", []):
        imgs = a.get("images") or []
        out.append(
            {
                "id": a["id"],
                "title": a.get("title", ""),
                "bullets": a.get("bullets", []),
                "has_image": bool(imgs),
                "images": [{"src": i.get("src"), "caption": i.get("caption")} for i in imgs],
            }
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _convert(src: Path, dst: Path) -> tuple[int, int]:
    """Convert to WebP <= MAX_WIDTH. Returns (width, height)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.webp")
    # Prefer cwebp, fall back to PIL, fall back to plain copy.
    cwebp = shutil.which("cwebp")
    if cwebp:
        r = subprocess.run(
            [cwebp, "-q", str(WEBP_QUALITY), "-resize", str(MAX_WIDTH), "0",
             str(src), "-o", str(tmp)],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            print(f"cwebp failed: {r.stderr[:300]}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            from PIL import Image

            im = Image.open(src).convert("RGB")
            if im.width > MAX_WIDTH:
                im = im.resize((MAX_WIDTH, int(im.height * MAX_WIDTH / im.width)))
            im.save(tmp, "WEBP", quality=WEBP_QUALITY)
        except ImportError:
            print("need cwebp or Pillow for conversion", file=sys.stderr)
            sys.exit(1)
    # read dimensions back
    try:
        from PIL import Image

        with Image.open(tmp) as im:
            w, h = im.size
    except ImportError:
        w, h = MAX_WIDTH, int(MAX_WIDTH * 9 / 16)
    tmp.replace(dst)
    return w, h


def cmd_register(args) -> int:
    path, issue = load_issue(args.date)
    src = Path(args.src)
    if not src.exists():
        print(f"source image not found: {src}", file=sys.stderr)
        return 1
    analyses = {a["id"]: a for a in issue.get("analysis", [])}
    a = analyses.get(args.analysis)
    if a is None:
        print(f"analysis id not found: {args.analysis}", file=sys.stderr)
        return 1

    name = img_name(args.analysis, args.prompt)
    dst = IMGROOT / args.date / name
    if dst.exists():
        print(f"already exists (idempotent skip): {dst.relative_to(ROOT)}")
    else:
        w, h = _convert(src, dst)
        print(f"saved {dst.relative_to(ROOT)} ({w}x{h})")

    # re-read dimensions if skipped
    try:
        from PIL import Image

        with Image.open(dst) as im:
            w, h = im.size
    except ImportError:
        w, h = MAX_WIDTH, int(MAX_WIDTH * 9 / 16)

    entry = {
        "src": f"/img/{args.date}/{name}",
        "caption": CAPTION,
        "alt": args.alt or "AI 생성 추상 일러스트",
        "width": w,
        "height": h,
    }
    imgs = a.get("images") or []
    # replace any entry for the same prompt hash, keep others
    imgs = [i for i in imgs if prompthash(args.prompt) not in i.get("src", "")]
    imgs.append(entry)
    a["images"] = imgs

    # provenance log (internal, not served)
    meta_dir = ROOT / "content" / "pipeline" / "images"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "date": args.date,
        "analysis": args.analysis,
        "src": entry["src"],
        "model": args.model,
        "prompt": args.prompt,
        "prompt_hash": prompthash(args.prompt),
        "alt": entry["alt"],
    }
    (meta_dir / f"{args.date}-{args.analysis}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    path.write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"registered image for analysis {args.analysis} in {path.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--date", required=True)
    r = sub.add_parser("register")
    r.add_argument("--date", required=True)
    r.add_argument("--analysis", required=True)
    r.add_argument("--src", required=True, help="generated image file (png/jpg)")
    r.add_argument("--prompt", required=True, help="final image prompt used")
    r.add_argument("--model", default="", help="image model name/version")
    r.add_argument("--alt", default="", help="alt text describing the illustration")
    args = ap.parse_args()
    if args.cmd == "plan":
        return cmd_plan(args.date)
    return cmd_register(args)


if __name__ == "__main__":
    sys.exit(main())
