#!/usr/bin/env python3
"""P11 회귀 테스트: P10 패널 검증 후속 권장 5건.

1. 피드백 커버리지 확대 (EMPTY-001 · TPL-001 · TAKEAWAY-DUP · QUOTA-001)
2. workflow LLM_TIMEOUT 고정 제거
3. 데드 코드 정리 (attach_sources buckets 파라미터 제거)
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import collect_structured_errors
from draft import render_feedback, attach_sources

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _a(aid, takeaway, url=None):
    return {
        "id": aid, "title": "제목", "bullets": ["불릿 하나"],
        "body": ["본문 첫 단락입니다. 자세한 내용을 담았습니다. 맥락을 설명합니다.",
                 "본문 둘째 단락입니다. 배경과 한계를 함께 적었습니다."],
        "takeaway": takeaway,
        "sources": [{"url": url}] if url else [],
    }


def _sidecar(errors) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"errors": errors}, f)
    f.close()
    return f.name


# --- 1a. collect: EMPTY-001 ---
iss = {"analysis": [_a("e1", "", "https://blog.a.com/p1")]}
errs = collect_structured_errors(iss, None)
emp = [e for e in errs if e.get("code") == "EMPTY-001"]
ok("P11 collect EMPTY-001", len(emp) == 1 and emp[0]["analysis_index"] == 0
   and emp[0]["analysis_id"] == "e1")

# --- 1b. collect: TPL-001 (블록리스트 문구) ---
iss = {"analysis": [_a("t1", "오늘 확인할 변경입니다. 자세히 보면 됩니다.",
                       "https://blog.a.com/p1")]}
errs = collect_structured_errors(iss, None)
tpl = [e for e in errs if e.get("code") == "TPL-001"]
ok("P11 collect TPL-001", len(tpl) == 1 and tpl[0]["analysis_id"] == "t1")
ok("P11 TPL-001 sidecar에 문구 미포함 (앵커 방지)",
   all("오늘 확인할 변경입니다" not in json.dumps(e, ensure_ascii=False) for e in errs))

# --- 1c. collect: TAKEAWAY-DUP (동일 시사점 3개) ---
_dup_tw = "새 모델이 공개됐습니다. 오늘 업무에 적용해 보세요."
iss = {"analysis": [
    _a("d1", _dup_tw, "https://blog.a.com/p1"),
    _a("d2", _dup_tw, "https://blog.b.com/p2"),
    _a("d3", _dup_tw, "https://blog.c.com/p3"),
]}
errs = collect_structured_errors(iss, None)
ok("P11 collect TAKEAWAY-DUP",
   any(e.get("code") == "TAKEAWAY-DUP" for e in errs))

# --- 1d. collect: QUOTA-001 (단일 도메인 100%) ---
iss = {"analysis": [
    _a("q1", "속도가 빨라졌습니다. 오늘부터 써 보세요.", "https://blog.a.com/p1"),
    _a("q2", "가격이 내려갔습니다. 예산을 다시 짜 보세요.", "https://blog.a.com/p2"),
    _a("q3", "새 기능이 추가됐습니다. 메뉴에서 확인해 보세요.", "https://blog.a.com/p3"),
]}
errs = collect_structured_errors(iss, None)
quo = [e for e in errs if e.get("code") == "QUOTA-001"]
ok("P11 collect QUOTA-001", len(quo) == 1 and quo[0].get("domain") == "blog.a.com")

# --- 1e. render: 신규 코드 4종 렌더링 ---
fb = render_feedback(_sidecar([{"code": "EMPTY-001", "analysis_index": 0,
                                 "analysis_id": "e1"}]))
ok("P11 render EMPTY-001", "takeaway(시사점)가 비어 있습니다" in fb and "e1" in fb)

fb = render_feedback(_sidecar([{"code": "TPL-001", "analysis_index": 0,
                                 "analysis_id": "t1"}]))
ok("P11 render TPL-001", "템플릿 문구" in fb and "t1" in fb)

fb = render_feedback(_sidecar([{"code": "TAKEAWAY-DUP"}]))
ok("P11 render TAKEAWAY-DUP", "서로 비슷하거나 같은 구조로 반복" in fb)

fb = render_feedback(_sidecar([{"code": "QUOTA-001", "domain": "blog.a.com"}]))
ok("P11 render QUOTA-001", "blog.a.com" in fb and "절반을 넘" in fb)

# --- 1f. end-to-end: TPL 이슈 → sidecar → 피드백에 문구 앵커 없음 ---
iss = {"analysis": [_a("t9", "오늘 확인할 변경입니다. 자세히 보면 됩니다.",
                       "https://blog.a.com/p1")]}
fb = render_feedback(_sidecar(collect_structured_errors(iss, None)))
ok("P11 e2e TPL 피드백 렌더링", "템플릿 문구" in fb)
ok("P11 e2e TPL 앵커 금지", "오늘 확인할 변경입니다" not in fb)

# --- 2. workflow: LLM_TIMEOUT 고정 제거 (attempt별 타임아웃 복원) ---
wf_text = (Path(__file__).resolve().parents[3] / ".github" / "workflows"
           / "daily-issue.yml").read_text(encoding="utf-8")
ok("P11 workflow LLM_TIMEOUT env 제거",
   not any(l.strip().startswith("LLM_TIMEOUT:") for l in wf_text.splitlines()))

# --- 3. attach_sources: buckets 파라미터 제거 (4개 위치 인자는 TypeError) ---
try:
    attach_sources({"analysis": []}, {"items": []}, None, [])
    ok("P11 attach_sources 구 시그니처 차단", False)
except TypeError:
    ok("P11 attach_sources 구 시그니처 차단", True)
out = attach_sources({"analysis": []}, {"items": []}, ref_table=[])
ok("P11 attach_sources 키워드 호출", out == {"analysis": []})

print(f"\n{__name__}: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
