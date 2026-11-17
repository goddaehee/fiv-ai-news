#!/usr/bin/env python3
"""P25: 발행 워크플로우 안에서 그날 호의 일러스트를 생성한다.

배경 (설계: hidden_files/p1-actions-image-integration.md):
- 기존에는 로컬 크론이 에이전트 육안 검수로 이미지를 만들어 PAT로 푸시
  했으나, PAT 401로 11/11~11/16호 36장이 6일째 미반영됐다.
- 발행 워크플로우는 GITHUB_TOKEN으로 커밋하므로, 초안 뒤 독립 스텝에서
  이미지를 생성하면 Publish 스텝이 이슈 JSON과 함께 커밋한다 (PAT 불요).

설계 원칙:
- 제공자 자동 선택은 draft.pick_key 패턴을 따른다. 이미지 전용 순서:
  GLM(CogView-4) → xAI(grok-imagine-image) → OpenAI. 셋 다 초안과 같은
  키를 쓰는 이미지 엔드포인트가 있어 신규 시크릿이 필요 없다.
  IMAGE_PROVIDER env로 선호 제공자를 지정할 수 있다.
- 프롬프트는 초안 LLM 호출 1회로 자동 생성한다. 규칙은 현행 로컬 크론
  지침 이식: 고유명사(회사명·인물명·제품명) 제거 → 추상 개념 장면,
  텍스트·숫자·사람·로고·차트 금지, 16:9.
- 비전 스크리닝: GLM 키가 있으면 GLM-4.6V-Flash(무료 티어)로 얼굴·
  텍스트·로고·차트 포함 여부를 검사한다. 걸리면 프롬프트를 강화해
  1회만 재생성하고, 다시 걸리거나 스크리닝 자체가 오류면 그 장은
  버린다 (잘못된 이미지보다 빈칸이 낫다는 현행 크론 원칙).
  GLM 키가 없으면 스크리닝 없이 진행하고 그 사실을 로그에 남긴다.
- 등록은 images.py register를 그대로 재사용한다 (WebP 1200px/q80,
  캡션 고정문, 프롬프트 해시 파일명으로 멱등).
- fail-open: 장별 실패는 건너뛰고, 전량 실패해도 종료 코드는 0이다.
  워크플로우 스텝도 continue-on-error로 격리해 발행을 막지 않는다.
  단, 대상이 있었는데 0장이면 ::warning:: 을 남겨 조용한 결호를 막는다.

Usage:
  python3 scripts/pipeline/gen_images.py --date 2026-11-18 [--max 7]
      [--no-screen]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import draft
import images

# 이미지 제공자. 순서는 설계 판정 (가격·호스트·키) 기준 glm → xai → openai.
# chat_url/model 기본값은 draft.PROVIDERS와 같은 값을 유지한다.
IMAGE_PROVIDERS = {
    "glm": {
        "env": ("GLM_API_KEY", "ZHIPU_API_KEY", "ZHIPUAI_API_KEY"),
        "url_env": "GLM_BASE_URL",
        "chat_url": "https://api.z.ai/api/paas/v4/chat/completions",
        "model_env": "GLM_IMAGE_MODEL",
        "model": "cogview-4-250304",
        "size": "1344x768",  # CogView-4의 16:9 계열
    },
    "xai": {
        "env": ("XAI_API_KEY", "GROK_API_KEY"),
        "url_env": "XAI_BASE_URL",
        "chat_url": "https://api.x.ai/v1/chat/completions",
        "model_env": "XAI_IMAGE_MODEL",
        "model": "grok-imagine-image",
        "size": None,
    },
    "openai": {
        "env": ("OPENAI_API_KEY",),
        "url_env": "OPENAI_BASE_URL",
        "chat_url": "https://api.openai.com/v1/chat/completions",
        "model_env": "OPENAI_IMAGE_MODEL",
        # 모델 세대 교체가 잦다 (gpt-image-1 2026-10-23 종료) — env로 교체.
        "model": "gpt-image-2",
        "size": "1536x1024",
    },
}

VISION_MODEL_DEFAULT = "glm-4.6v-flash"

# 현행 로컬 크론 지침(고유명사 제거·추상화·금지 요소)을 LLM 지시로 이식.
PROMPT_SYSTEM = """You create English image prompts for abstract editorial illustrations of a Korean AI news digest.

For each analysis item (id, Korean title, bullets):
- Remove ALL proper nouns: company names, person names, product names, brand names, service names.
- Turn the remaining core concept into one concrete visual scene described in English.
- Style: flat abstract illustration, soft muted colors, simple geometric shapes, wide 16:9 composition.
- STRICTLY FORBIDDEN in the image: text, letters, numbers, words, people, faces, human figures, logos, brand marks, charts, graphs, tables, data plots, readable screens.
- Each prompt is 1-2 English sentences and ends with: "flat abstract illustration, wide 16:9 composition, no text, no people, no logos, no charts".
- alt: one short Korean sentence describing the illustration, without proper nouns.

Output JSON only: {"prompts": [{"id": "<id>", "prompt": "<english prompt>", "alt": "<korean alt>"}]}
One entry per input item, with the same ids, in the same order."""

SCREEN_TEXT = (
    "Look at this illustration. Does it contain ANY of the following? "
    "(1) a person, face, or human figure "
    "(2) text, letters, numbers, or words "
    "(3) a logo or brand mark "
    "(4) a chart, graph, table, or data plot. "
    'Answer with JSON only: {"violation": true} if any are present, '
    '{"violation": false} if none are present.'
)

# 스크리닝에 걸렸을 때 재생성 프롬프트에 덧붙이는 강화 문구.
STRONG_SUFFIX = (
    " Purely abstract geometric shapes, soft gradients and simple symbolic "
    "forms only. Absolutely no text, no letters, no numbers, no people, "
    "no faces, no logos, no charts."
)


class ImageError(Exception):
    """제공자 호출·응답 파싱 실패. 장 단위로 격리해 흡수한다."""


def _env_key(env_names) -> str | None:
    return next(
        (os.environ[k].strip() for k in env_names
         if os.environ.get(k) and os.environ[k].strip()),
        None,
    )


def _chat_url(spec: dict) -> str:
    url = (os.environ.get(spec["url_env"]) or spec["chat_url"]).strip()
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"
    return url


def pick_image_providers() -> list[dict]:
    """draft.pick_key와 같은 패턴: 키가 있는 제공자를 이미지 순서로 반환.

    IMAGE_PROVIDER env가 있으면 그 제공자를 맨 앞에 둔다."""
    order = ["glm", "xai", "openai"]
    want = (os.environ.get("IMAGE_PROVIDER") or "").strip().lower()
    if want in IMAGE_PROVIDERS:
        order = [want] + [p for p in order if p != want]
    out: list[dict] = []
    for name in order:
        spec = IMAGE_PROVIDERS[name]
        key = _env_key(spec["env"])
        if not key:
            continue
        chat_url = _chat_url(spec)
        out.append(
            {
                "name": name,
                "key": key,
                "url": chat_url[: -len("/chat/completions")] + "/images/generations",
                "model": (os.environ.get(spec["model_env"]) or spec["model"]).strip(),
                "size": spec["size"],
            }
        )
    return out


def pick_vision() -> tuple[str, str, str] | None:
    """비전 스크리닝용 GLM (key, chat_url, model). GLM 키가 없으면 None."""
    spec = IMAGE_PROVIDERS["glm"]
    key = _env_key(spec["env"])
    if not key:
        return None
    model = (os.environ.get("GLM_VISION_MODEL") or VISION_MODEL_DEFAULT).strip()
    return key, _chat_url(spec), model


def _post_json(url: str, key: str, payload: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl.create_default_context()) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ImageError(f"HTTP {e.code} from {url.split('?')[0]}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ImageError(f"request failed for {url.split('?')[0]}: {e}") from e


def generate_image(prov: dict, prompt: str) -> tuple[str, object]:
    """제공자 이미지 API 1회 호출. ("url", str) 또는 ("bytes", bytes) 반환."""
    payload: dict = {"model": prov["model"], "prompt": prompt, "n": 1}
    if prov["name"] == "xai":
        payload["response_format"] = "url"
    elif prov.get("size"):
        payload["size"] = prov["size"]
    resp = _post_json(prov["url"], prov["key"], payload, timeout=180)
    data = resp.get("data") or []
    if not data or not isinstance(data[0], dict):
        raise ImageError(f"{prov['name']}: empty data in image response")
    item = data[0]
    if item.get("url"):
        return "url", str(item["url"])
    if item.get("b64_json"):
        try:
            return "bytes", base64.b64decode(item["b64_json"])
        except Exception as e:
            raise ImageError(f"{prov['name']}: bad b64_json in image response") from e
    raise ImageError(f"{prov['name']}: no url/b64_json in image response")


def _download(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "fiv-pipeline/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl.create_default_context()) as res:
            return res.read()
    except Exception as e:
        raise ImageError(f"download failed for generated image: {e}") from e


def _suffix_for(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def make_prompts(targets: list[dict]) -> dict[str, dict]:
    """초안 LLM 1회 호출로 분석별 이미지 프롬프트를 만든다.

    반환: {analysis_id: {"prompt": ..., "alt": ...}}. 호출·파싱이 실패하면
    빈 dict (호출자가 0장으로 fail-open 처리한다)."""
    picked = draft.pick_key()
    if picked is None:
        print("[gen-images] no LLM key for prompt generation", flush=True)
        return {}
    _name, key, url, model = picked
    user = json.dumps(
        [
            {"id": a.get("id"), "title": a.get("title", ""),
             "bullets": a.get("bullets", [])}
            for a in targets
        ],
        ensure_ascii=False,
    )
    try:
        text = draft.chat(url, key, model, user, system=PROMPT_SYSTEM,
                          temperature=0.7, timeout=180)
        parsed = draft.extract_json(text)
    except (SystemExit, Exception) as e:  # draft.chat은 HTTP 오류 시 SystemExit
        print(f"[gen-images] prompt generation failed: {e}", flush=True)
        return {}
    valid_ids = {a.get("id") for a in targets}
    out: dict[str, dict] = {}
    for entry in parsed.get("prompts") or []:
        if not isinstance(entry, dict):
            continue
        aid = entry.get("id")
        prompt = str(entry.get("prompt") or "").strip()
        if aid in valid_ids and prompt:
            out[aid] = {"prompt": prompt, "alt": str(entry.get("alt") or "").strip()}
    return out


def screen_image(vision: tuple[str, str, str], *, url: str | None = None,
                 data: bytes | None = None) -> bool | None:
    """비전 스크리닝. True=통과, False=금지 요소 발견, None=판정 불가(오류).

    호출자는 None을 "그 장을 버린다"로 처리한다 (fail-closed per image)."""
    key, chat_url, model = vision
    if url:
        img_ref = url
    elif data is not None:
        mime = {".png": "image/png", ".jpg": "image/jpeg",
                ".webp": "image/webp"}[_suffix_for(data)]
        img_ref = f"data:{mime};base64," + base64.b64encode(data).decode()
    else:
        return None
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": img_ref}},
                    {"type": "text", "text": SCREEN_TEXT},
                ],
            }
        ],
    }
    try:
        resp = _post_json(chat_url, key, payload, timeout=120)
        content = resp["choices"][0]["message"].get("content") or ""
    except (ImageError, KeyError, IndexError, TypeError):
        return None
    m = re.search(r'"violation"\s*:\s*(true|false)', content)
    if not m:
        return None
    return m.group(1) == "false"


def _register(date: str, analysis_id: str, src: Path, prompt: str,
              model_label: str, alt: str) -> bool:
    ns = argparse.Namespace(date=date, analysis=analysis_id, src=str(src),
                            prompt=prompt, model=model_label, alt=alt)
    try:
        return images.cmd_register(ns) == 0
    except SystemExit as e:  # _convert가 실패 시 sys.exit(1)
        print(f"[gen-images] register failed for {analysis_id}: exit {e.code}",
              flush=True)
        return False


def run(date: str, max_images: int = 7, use_screen: bool = True) -> int:
    """그날 호의 이미지 없는 analysis에 일러스트를 채운다. 항상 0 반환."""
    issue_path = images.ISSUES / f"{date}.json"
    if not issue_path.exists():
        print(f"[gen-images] no issue file for {date} — nothing to do", flush=True)
        return 0
    try:
        issue = json.loads(issue_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"::warning::[gen-images] issue JSON unreadable ({date}): {e}",
              flush=True)
        return 0
    targets = [a for a in issue.get("analysis", [])
               if not (a.get("images") or [])][:max_images]
    if not targets:
        print(f"[gen-images] {date}: all analyses already have images", flush=True)
        return 0
    providers = pick_image_providers()
    if not providers:
        print(f"::warning::[gen-images] no image provider key — "
              f"{len(targets)} image(s) skipped for {date}", flush=True)
        return 0
    prompts = make_prompts(targets)
    if not prompts:
        print(f"::warning::[gen-images] prompt generation produced nothing — "
              f"{len(targets)} image(s) skipped for {date}", flush=True)
        return 0
    vision = pick_vision() if use_screen else None
    if use_screen and vision is None:
        print("[gen-images] no GLM key — vision screening skipped", flush=True)

    fails: dict[str, int] = {}
    generated = 0
    with tempfile.TemporaryDirectory(prefix="fiv-genimg-") as tmp:
        tmpdir = Path(tmp)
        for a in targets:
            aid = a.get("id")
            spec = prompts.get(aid)
            if not spec:
                print(f"[gen-images] no prompt for {aid} — skipped", flush=True)
                continue
            done = False
            for attempt in (1, 2):
                prompt = spec["prompt"] if attempt == 1 else spec["prompt"] + STRONG_SUFFIX
                got = None
                for prov in providers:
                    if fails.get(prov["name"], 0) >= 2:
                        continue
                    try:
                        kind, payload = generate_image(prov, prompt)
                        got = (prov, kind, payload)
                        break
                    except ImageError as e:
                        fails[prov["name"]] = fails.get(prov["name"], 0) + 1
                        print(f"[gen-images] {prov['name']} generation failed "
                              f"({aid}): {e}", flush=True)
                if got is None:
                    break
                prov, kind, payload = got
                try:
                    data = _download(str(payload)) if kind == "url" else payload
                except ImageError as e:
                    print(f"[gen-images] {e}", flush=True)
                    break
                if vision is not None:
                    verdict = screen_image(
                        vision,
                        url=str(payload) if kind == "url" else None,
                        data=data if kind != "url" else None,
                    )
                    if verdict is None:
                        print(f"[gen-images] screening error for {aid} — "
                              "discarding image (fail-closed per image)", flush=True)
                        break
                    if verdict is False:
                        if attempt == 1:
                            print(f"[gen-images] screening violation for {aid} — "
                                  "regenerating once with a stronger prompt",
                                  flush=True)
                            continue
                        print(f"[gen-images] screening violation again for {aid} "
                              "— skipping", flush=True)
                        break
                src = tmpdir / f"{aid}-{attempt}{_suffix_for(data)}"
                src.write_bytes(data)  # type: ignore[arg-type]
                if _register(date, str(aid), src, prompt,
                             f"{prov['name']}/{prov['model']}",
                             spec.get("alt") or ""):
                    generated += 1
                    done = True
                break
            if not done:
                print(f"[gen-images] {aid}: no image registered", flush=True)
    print(f"[gen-images] {date}: {generated}/{len(targets)} image(s) generated",
          flush=True)
    if generated == 0:
        print(f"::warning::[gen-images] 0 images generated for {date} "
              f"(targets: {len(targets)})", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="issue date, YYYY-MM-DD")
    ap.add_argument("--max", type=int, default=7,
                    help="max images to generate (default 7)")
    ap.add_argument("--no-screen", action="store_true",
                    help="skip vision screening")
    args = ap.parse_args()
    return run(args.date, max_images=args.max, use_screen=not args.no_screen)


if __name__ == "__main__":
    sys.exit(main())
