#!/usr/bin/env python3
"""P25 테스트: gen_images.py — Actions 이미지 생성 통합 1단계.

검증 범위:
1. 제공자 자동 선택 (pick_image_providers): 키 있는 제공자만, 순서
   glm → xai → openai, IMAGE_PROVIDER 선호, GLM_BASE_URL에서 이미지
   엔드포인트 파생.
2. generate_image 응답 파싱: url형(GLM·xAI)·b64형(OpenAI)·빈 응답 오류.
   제공자별 payload (GLM size, xAI response_format).
3. make_prompts: LLM JSON 파싱, 입력에 없는 id 제거, 호출 실패 시 빈 dict.
4. screen_image 판정 파싱: violation true/false/판정 불가(None).
5. run() end-to-end (전부 스텁): register 재사용으로 WebP·이슈 JSON·
   메타가 생기는지, 스크리닝 위반 시 1회 재생성 후 스킵, 스크리닝
   오류 시 그 장 폐기, 키 없음·호 파일 없음에서 fail-open(종료 0).
"""

import base64
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import draft
import gen_images as gen
import images

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


_ALL_KEYS = [
    "GLM_API_KEY", "ZHIPU_API_KEY", "ZHIPUAI_API_KEY", "GLM_BASE_URL",
    "GLM_IMAGE_MODEL", "GLM_VISION_MODEL",
    "XAI_API_KEY", "GROK_API_KEY", "XAI_BASE_URL", "XAI_IMAGE_MODEL",
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_IMAGE_MODEL",
    "IMAGE_PROVIDER", "LLM_PROVIDER",
]


@contextlib.contextmanager
def clean_env(**set_vars):
    saved = {k: os.environ.get(k) for k in _ALL_KEYS}
    for k in _ALL_KEYS:
        os.environ.pop(k, None)
    os.environ.update(set_vars)
    try:
        yield
    finally:
        for k in _ALL_KEYS:
            if saved[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]


# ---------- 1. 제공자 선택 ----------
with clean_env(GLM_API_KEY="glm-key"):
    provs = gen.pick_image_providers()
    ok("선택: GLM 키만 있으면 glm 1개", [p["name"] for p in provs] == ["glm"])
    ok("선택: GLM 이미지 URL 파생",
       provs[0]["url"] == "https://api.z.ai/api/paas/v4/images/generations")
    ok("선택: GLM 기본 모델", provs[0]["model"] == "cogview-4-250304")

with clean_env(GLM_API_KEY="g", XAI_API_KEY="x", OPENAI_API_KEY="o"):
    ok("선택: 기본 순서 glm→xai→openai",
       [p["name"] for p in gen.pick_image_providers()] == ["glm", "xai", "openai"])

with clean_env(GLM_API_KEY="g", XAI_API_KEY="x", IMAGE_PROVIDER="xai"):
    ok("선택: IMAGE_PROVIDER 선호가 맨 앞",
       [p["name"] for p in gen.pick_image_providers()] == ["xai", "glm"])

with clean_env(GLM_API_KEY="g", GLM_BASE_URL="https://example.com/api/paas/v4"):
    ok("선택: GLM_BASE_URL(베이스형) 파생",
       gen.pick_image_providers()[0]["url"]
       == "https://example.com/api/paas/v4/images/generations")

with clean_env(GLM_API_KEY="g",
               GLM_BASE_URL="https://example.com/api/paas/v4/chat/completions"):
    ok("선택: GLM_BASE_URL(chat URL형) 파생",
       gen.pick_image_providers()[0]["url"]
       == "https://example.com/api/paas/v4/images/generations")

with clean_env():
    ok("선택: 키 없으면 빈 목록", gen.pick_image_providers() == [])
    ok("선택: 키 없으면 비전도 None", gen.pick_vision() is None)

with clean_env(ZHIPU_API_KEY="z"):
    v = gen.pick_vision()
    ok("선택: ZHIPU 별칭 키로 비전 구성", v is not None and v[0] == "z"
       and v[2] == "glm-4.6v-flash")


# ---------- 2. generate_image 파싱·payload ----------
def stub_post_factory(resp, capture=None):
    def _stub(url, key, payload, timeout=120):
        if capture is not None:
            capture.update({"url": url, "payload": payload})
        return resp
    return _stub


_orig_post = gen._post_json
try:
    cap: dict = {}
    gen._post_json = stub_post_factory(
        {"data": [{"url": "https://cdn.example/x.png"}]}, cap)
    prov = {"name": "glm", "key": "k", "url": "https://api.z.ai/images",
            "model": "cogview-4-250304", "size": "1344x768"}
    kind, payload = gen.generate_image(prov, "abstract shapes")
    ok("생성: GLM url 응답 파싱", kind == "url" and payload == "https://cdn.example/x.png")
    ok("생성: GLM payload 모델·사이즈",
       cap["payload"]["model"] == "cogview-4-250304"
       and cap["payload"]["size"] == "1344x768")

    cap = {}
    gen._post_json = stub_post_factory(
        {"data": [{"url": "https://cdn.example/y.jpg"}]}, cap)
    prov = {"name": "xai", "key": "k", "url": "https://api.x.ai/images",
            "model": "grok-imagine-image", "size": None}
    kind, _ = gen.generate_image(prov, "abstract shapes")
    ok("생성: xAI url 응답 + response_format",
       kind == "url" and cap["payload"].get("response_format") == "url")

    raw = b"\x89PNG\r\n\x1a\nfake"
    gen._post_json = stub_post_factory(
        {"data": [{"b64_json": base64.b64encode(raw).decode()}]})
    prov = {"name": "openai", "key": "k", "url": "https://api.openai.com/images",
            "model": "gpt-image-2", "size": "1536x1024"}
    kind, payload = gen.generate_image(prov, "abstract shapes")
    ok("생성: OpenAI b64 응답 파싱", kind == "bytes" and payload == raw)

    gen._post_json = stub_post_factory({"data": []})
    try:
        gen.generate_image(prov, "x")
        ok("생성: 빈 data는 ImageError", False)
    except gen.ImageError:
        ok("생성: 빈 data는 ImageError", True)
finally:
    gen._post_json = _orig_post


# ---------- 3. make_prompts ----------
_targets = [
    {"id": "a1", "title": "제목1", "bullets": ["b1"]},
    {"id": "a2", "title": "제목2", "bullets": ["b2"]},
]
_orig_pick, _orig_chat = draft.pick_key, draft.chat
try:
    draft.pick_key = lambda prefer=None: ("glm", "k", "https://x/chat/completions", "m")
    draft.chat = lambda *a, **k: json.dumps({"prompts": [
        {"id": "a1", "prompt": "abstract waves", "alt": "추상적인 파도"},
        {"id": "bogus", "prompt": "should be dropped", "alt": "x"},
        {"id": "a2", "prompt": "", "alt": "빈 프롬프트"},
    ]})
    got = gen.make_prompts(_targets)
    ok("프롬프트: 유효 id만 매핑", set(got) == {"a1"})
    ok("프롬프트: 내용·alt 보존",
       got["a1"]["prompt"] == "abstract waves" and got["a1"]["alt"] == "추상적인 파도")

    def _boom(*a, **k):
        raise SystemExit("LLM HTTP 500")
    draft.chat = _boom
    ok("프롬프트: LLM 실패 시 빈 dict (fail-open)", gen.make_prompts(_targets) == {})

    draft.pick_key = lambda prefer=None: None
    ok("프롬프트: 키 없으면 빈 dict", gen.make_prompts(_targets) == {})
finally:
    draft.pick_key, draft.chat = _orig_pick, _orig_chat


# ---------- 4. screen_image 판정 파싱 ----------
try:
    gen._post_json = stub_post_factory(
        {"choices": [{"message": {"content": '{"violation": true}'}}]})
    ok("스크리닝: violation true → False(불통과)",
       gen.screen_image(("k", "https://x/chat/completions", "m"),
                        url="https://cdn.example/x.png") is False)
    gen._post_json = stub_post_factory(
        {"choices": [{"message": {"content": '검사 결과: {"violation": false}'}}]})
    ok("스크리닝: violation false → True(통과)",
       gen.screen_image(("k", "https://x/chat/completions", "m"),
                        url="https://cdn.example/x.png") is True)
    gen._post_json = stub_post_factory(
        {"choices": [{"message": {"content": "판정할 수 없습니다"}}]})
    ok("스크리닝: 파싱 불가 → None",
       gen.screen_image(("k", "https://x/chat/completions", "m"),
                        url="https://cdn.example/x.png") is None)

    def _err(*a, **k):
        raise gen.ImageError("HTTP 404")
    gen._post_json = _err
    ok("스크리닝: API 오류 → None",
       gen.screen_image(("k", "https://x/chat/completions", "m"),
                        url="https://cdn.example/x.png") is None)
finally:
    gen._post_json = _orig_post


# ---------- 5. run() end-to-end (스텁) ----------
def _tiny_png() -> bytes:
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (120, 140, 180)).save(buf, "PNG")
    return buf.getvalue()


def _setup_issue(tmp: Path, date: str, analyses: list) -> None:
    (tmp / "content" / "issues").mkdir(parents=True)
    (tmp / "content" / "issues" / f"{date}.json").write_text(
        json.dumps({"date": date, "analysis": analyses}, ensure_ascii=False),
        encoding="utf-8")


@contextlib.contextmanager
def patched_images_root(tmp: Path):
    saved = (images.ROOT, images.ISSUES, images.IMGROOT)
    images.ROOT = tmp
    images.ISSUES = tmp / "content" / "issues"
    images.IMGROOT = tmp / "public" / "img"
    try:
        yield
    finally:
        images.ROOT, images.ISSUES, images.IMGROOT = saved


DATE = "2026-11-18"
_fake_prov = [{"name": "glm", "key": "k", "url": "https://img.example/gen",
               "model": "cogview-4-250304", "size": "1344x768"}]

_orig_funcs = (gen.pick_image_providers, gen.make_prompts, gen.generate_image,
               gen.pick_vision, gen.screen_image)
try:
    # 5a. 정상 경로: 1개는 이미 이미지 있음(대상 제외), 1개 생성·등록
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_issue(tmp, DATE, [
            {"id": "has", "title": "t", "bullets": [],
             "images": [{"src": "/img/x.webp"}]},
            {"id": "need", "title": "t2", "bullets": ["b"]},
        ])
        gen.pick_image_providers = lambda: _fake_prov
        gen.make_prompts = lambda targets: {
            "need": {"prompt": "abstract waves, flat illustration", "alt": "추상 파도"}}
        gen.generate_image = lambda prov, prompt: ("bytes", _tiny_png())
        gen.pick_vision = lambda: None  # 스크리닝 없음 경로
        with patched_images_root(tmp):
            rc = gen.run(DATE)
            issue = json.loads(
                (tmp / "content" / "issues" / f"{DATE}.json").read_text("utf-8"))
        by_id = {a["id"]: a for a in issue["analysis"]}
        ok("run: 종료 코드 0", rc == 0)
        ok("run: 대상에만 이미지 등록",
           len(by_id["need"].get("images") or []) == 1
           and len(by_id["has"].get("images") or []) == 1)
        entry = by_id["need"]["images"][0]
        ok("run: 캡션 고정문", entry["caption"] == "AI 생성 일러스트 (실제 사진 아님)")
        webp = tmp / "public" / entry["src"].lstrip("/")
        ok("run: WebP 파일 실재", webp.is_file())
        meta = tmp / "content" / "pipeline" / "images" / f"{DATE}-need.json"
        ok("run: 출처 메타 기록", meta.is_file()
           and json.loads(meta.read_text("utf-8"))["model"] == "glm/cogview-4-250304")

    # 5b. 스크리닝 위반 → 1회 재생성 → 재위반이면 스킵 (생성 2회 호출)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_issue(tmp, DATE, [{"id": "need", "title": "t", "bullets": []}])
        calls = {"n": 0}

        def _counting_gen(prov, prompt):
            calls["n"] += 1
            return ("bytes", _tiny_png())
        gen.generate_image = _counting_gen
        gen.pick_vision = lambda: ("k", "https://x/chat/completions", "m")
        gen.screen_image = lambda vision, url=None, data=None: False
        with patched_images_root(tmp):
            rc = gen.run(DATE)
            issue = json.loads(
                (tmp / "content" / "issues" / f"{DATE}.json").read_text("utf-8"))
        ok("run: 위반 시 재생성 1회 후 스킵",
           rc == 0 and calls["n"] == 2
           and not (issue["analysis"][0].get("images") or []))

    # 5c. 스크리닝 오류(None) → 재생성 없이 그 장 폐기
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_issue(tmp, DATE, [{"id": "need", "title": "t", "bullets": []}])
        calls = {"n": 0}

        def _counting_gen2(prov, prompt):
            calls["n"] += 1
            return ("bytes", _tiny_png())
        gen.generate_image = _counting_gen2
        gen.screen_image = lambda vision, url=None, data=None: None
        with patched_images_root(tmp):
            rc = gen.run(DATE)
            issue = json.loads(
                (tmp / "content" / "issues" / f"{DATE}.json").read_text("utf-8"))
        ok("run: 스크리닝 오류 시 폐기(재생성 없음)",
           rc == 0 and calls["n"] == 1
           and not (issue["analysis"][0].get("images") or []))

    # 5d. fail-open: 제공자 없음 / 호 파일 없음
    gen.pick_image_providers = lambda: []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_issue(tmp, DATE, [{"id": "need", "title": "t", "bullets": []}])
        with patched_images_root(tmp):
            ok("run: 키 없으면 0 반환", gen.run(DATE) == 0)
            ok("run: 호 파일 없으면 0 반환", gen.run("1999-01-01") == 0)
finally:
    (gen.pick_image_providers, gen.make_prompts, gen.generate_image,
     gen.pick_vision, gen.screen_image) = _orig_funcs


print(f"P25 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
