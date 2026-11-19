#!/usr/bin/env python3
"""P23 회귀 테스트: 본문 밀도 강화 (5차 평가 P5).

- 프롬프트: 3문단·문단당 200~250자·합계 700자 목표·600자 미만 미달,
  문단 역할 재배정(사실+스펙 / 회사 발표 수치+측정 조건 / 배경+한계·전망),
  자기 검수 지시. 작성 예시는 650자 이상 완성형 3문단.
- 재료: _item_payload summary 절단 180자 → 450자.
- BODY-TOTAL 3종 세트: collect_structured_errors 수집 + render_feedback
  렌더링 + attempt-aware 2단계 게이트 (최종 전 error·최종은 500자 하한만
  error·monitor는 warning만). 과거 호 보호: monitor 모드에서 error 없음.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import PROMPT, render_feedback  # noqa: E402
from validate import check_quality, collect_structured_errors  # noqa: E402

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# --- 1. 프롬프트: 700자 목표·600자 미달·3문단 역할 재배정 ---
ok("프롬프트: 700자 목표", "700자 목표" in PROMPT)
ok("프롬프트: 600자 미만이면 미달", "600자 미만이면 미달" in PROMPT)
ok("프롬프트: 문단당 200~250자", "200~250자" in PROMPT)
# 품질 루프 2026-11-19: "2~3문장"은 문장당 ~50자 기준으로 200자에 못 미쳐
# 11-17호 문단이 91~173자에 머물렀고 P23 최종 하한 500자에 걸려 11-18·11-19
# 발행이 실패했다. 작성 예시(문단당 5~6문장)와 지시를 일치시킨다.
ok("프롬프트: 문단당 4~6문장 (예시와 일치)", "문단당 4~6문장" in PROMPT)
ok("프롬프트: 본문 spec에 2~3문장 잔재 없음", "body 3문단(문단당 2~3문장" not in PROMPT)
ok("프롬프트: 3문단 고정 (3~4문단 잔재 없음)", "body 3문단(" in PROMPT and "3~4문단" not in PROMPT)
ok("프롬프트: 1단 사실+스펙", "첫 문단=무슨 일인가(핵심 사실 + 기술 스펙" in PROMPT)
ok("프롬프트: 2단 회사 발표 수치+측정 조건", "둘째 문단=회사 발표 수치와 그 측정 조건" in PROMPT)
ok("프롬프트: 발표·외부 측정 분리 재강조", "회사 발표와 외부 측정을 한 단에 섞지 않는다" in PROMPT)
ok("프롬프트: 3단 배경+한계·반론·전망", "셋째 문단=배경·맥락 + 한계·반론·전망" in PROMPT)
ok("프롬프트: 숫자 복사 규칙", "숫자는 입력의 number_mentions에서 복사해 쓰고" in PROMPT)
ok("프롬프트: 자기 검수 지시", "출력 전에 기사마다 본문 글자 수를 셉니다" in PROMPT)

# --- 2. 작성 예시: 650자 이상 완성형 3문단 ---
_m = re.search(r"\[작성 예시.*?body: \"(.*?)\"\ntakeaway:", PROMPT, re.S)
ok("예시 본문 추출 가능", _m is not None)
if _m:
    _ex = _m.group(1).replace("\\n", "\n")
    _paras = [p for p in _ex.split("\n\n") if p.strip()]
    ok("예시 본문 합계 650자 이상", len(_ex.replace("\n", "")) >= 650)
    ok("예시 본문 3문단", len(_paras) == 3)
    ok("예시 본문 문단당 200자 이상", all(len(p) >= 200 for p in _paras))
    ok("예시 본문 문단당 4문장 이상 (지시와 일치)", all(p.count(".") >= 4 for p in _paras))
    ok("예시 2문단은 측정 조건 문단", "과제 묶음" in _paras[1] and "측정" in _paras[1] or "잰 값" in _paras[1])
    ok("예시 3문단은 한계 문단", "확인되지 않았다" in _paras[2])

# --- 3. 재료: summary 절단 450자 ---
_draft_src = (Path(__file__).resolve().parents[1] / "draft.py").read_text(encoding="utf-8")
ok("summary 절단 450자", "full_summary[:450]" in _draft_src)
ok("summary 절단 180자 잔재 없음", "full_summary[:180]" not in _draft_src)


_SENTENCES = [
    "OpenAI가 새 모델을 공개했습니다. 응답 속도는 2배 빨라지고 가격은 30% 내렸습니다.",
    "새 모델은 기존 모델과 같은 방식으로 호출할 수 있고, 문서도 같은 날 함께 열렸습니다.",
    "회사는 이번 공개를 개발자 대상 행사에서 발표했으며, 적용 대상은 이용자 전체라고 밝혔습니다.",
    "이전 모델과 비교하면 생성 속도가 크게 올랐고, 이번 수치는 회사가 공개한 과제 100개로 잰 평균값입니다.",
    "과제 묶음은 영어 과제로 구성돼 있고, 긴 문서 과제나 다른 언어 과제는 포함되지 않았습니다.",
    "다만 평가는 영어 과제뿐이라 다른 언어에서는 확인되지 않았고, 가격은 API 호출 기준이라 구독 요금과는 다릅니다.",
    "외부 독립 측정은 아직 공개되지 않았고, 회사가 밝힌 수치만으로 실제 효과를 단정할 수는 없습니다.",
    "도입을 검토하는 쪽은 영어 외 과제 점수와 실제 호출량을 함께 확인하면 됩니다.",
    "기존 모델을 쓰던 이용자는 설정을 바꾸지 않고도 새 모델을 선택할 수 있습니다.",
]


def _make_body(target: int) -> list[str]:
    """목표 글자수에 맞는 실제 문장 본문 2문단을 만든다.
    반복 문자 픽스처는 depth·BODY-FRAG·KEYNUMS-LINK를 건드려 BODY-TOTAL만
    격리할 수 없으므로, 숫자·한계·완결 문장을 갖춘 실제 문장을 쓴다."""
    paras = ["", ""]
    i = 0
    while len(" ".join(paras)) < target:
        paras[i % 2] += _SENTENCES[i % len(_SENTENCES)] + " "
        i += 1
    return [p.strip() for p in paras]


def _issue(body, n_sources=1):
    srcs = [{"handle": "OpenAI", "url": "https://openai.com/a", "kind": "doc"}]
    if n_sources >= 2:
        srcs.append({"handle": "Anthropic", "url": "https://anthropic.com/b", "kind": "doc"})
    if n_sources >= 3:
        srcs.append({"handle": "Google", "url": "https://google.com/c", "kind": "doc"})
    return {
        "date": "2026-11-17", "title": "제목", "heroline": "h", "dek": "d",
        "tag": "AI", "briefMin": 5, "readMin": 10,
        "briefing": [{"id": "a", "headline": "OpenAI 새 모델 공개", "summary": "요약입니다."}],
        "keywords": ["OpenAI"], "mainEvent": "OpenAI 새 모델 공개 행사",
        "keynums": [{"val": "30%", "lab": "성능 향상", "sub": "OpenAI 발표"}],
        "timeline": [{"t": "11/17 09:00", "d": "모델 공개"}],
        "intro": "11월 17일 월요일 발행. 오늘의 소식입니다.",
        "analysis": [{
            "id": "a", "title": "1. OpenAI 새 모델", "bullets": ["핵심 사실 하나", "둘째 사실"],
            "body": body,
            "takeaway": "속도가 바뀐 점이 도입 비용 판단에 중요합니다. 적용 전에 자기 과제 점수와 실제 호출량을 먼저 확인하면 됩니다.",
            "tags": ["OpenAI"], "sources": srcs,
        }],
        "mood": {"shift": "s", "grow": "g", "caution": "c", "heat": "h"},
        "tips": [{"title": "팁 제목", "body": "팁 본문입니다.", "via": "OpenAI"}],
        "method": "m",
    }


# --- 4. BODY-TOTAL 수집 ---
_thin_body = _make_body(521)
_thin_len = len(" ".join(_thin_body))
ok("픽스처: thin 본문이 500~599자 구간", 500 <= _thin_len < 600)
thin = _issue(_thin_body)
bt = [e for e in collect_structured_errors(thin, None) if e.get("code") == "BODY-TOTAL"]
ok("수집: thin 본문에 BODY-TOTAL 1건", len(bt) == 1)
ok("수집: length/deficit/required", len(bt) == 1 and bt[0]["length"] == _thin_len
   and bt[0]["required"] == 600 and bt[0]["deficit"] == 600 - _thin_len)
ok("수집: analysis_id", len(bt) == 1 and bt[0]["analysis_id"] == "a")
_dense_body = _make_body(621)
ok("픽스처: dense 본문이 600자 이상", len(" ".join(_dense_body)) >= 600)
dense = _issue(_dense_body, n_sources=3)
ok("수집: dense 본문에 BODY-TOTAL 없음",
   not [e for e in collect_structured_errors(dense, None) if e.get("code") == "BODY-TOTAL"])
ok("수집: 빈 본문은 BODY-TOTAL 없음",
   not [e for e in collect_structured_errors(_issue([""]), None) if e.get("code") == "BODY-TOTAL"])

# --- 5. BODY-TOTAL 렌더링 ---
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump({"errors": bt}, f, ensure_ascii=False)
    _sidecar = f.name
fb = render_feedback(_sidecar)
ok("렌더링: 600자 이상 처방", "600자 이상이 필요합니다" in fb)
ok("렌더링: 숫자 새로 만들지 말기", "숫자는 새로 만들지 말고" in fb)
ok("렌더링: 문단 쪼개기 금지", "문단을 쪼개 개수로 채우지 마세요" in fb)
ok("렌더링: NUMBERS 동시 발생 우선순위", "입력에 근거한 숫자만 남기는 것을 우선합니다" in fb)
ok("렌더링: analysis id 포함", '"a"' in fb)

# --- 6. attempt-aware 게이트 ---
_qe, _qw = check_quality(thin, None, None, "2026-11-17", attempt=1, attempts_total=3)
ok("게이트: attempt 1에서 thin → error", any("BODY-TOTAL" in e for e in _qe))
_qe2, _qw2 = check_quality(thin, None, None, "2026-11-17", attempt=2, attempts_total=3)
ok("게이트: attempt 2에서 thin → error", any("BODY-TOTAL" in e for e in _qe2))
_qe3, qw3 = check_quality(thin, None, None, "2026-11-17", attempt=3, attempts_total=3)
ok("게이트: attempt 3에서 thin → BODY-TOTAL error 없음", not any("BODY-TOTAL" in e for e in _qe3))
ok("게이트: attempt 3에서 thin → 밀도 warning", any("밀도 부족" in w for w in qw3))
_floor_body = _make_body(401)
ok("픽스처: floor 본문이 500자 미만", len(" ".join(_floor_body)) < 500)
floor = _issue(_floor_body)
_qef, _ = check_quality(floor, None, None, "2026-11-17", attempt=3, attempts_total=3)
ok("게이트: attempt 3에서도 floor → error (500자 하한)", any("BODY-TOTAL" in e for e in _qef))
_qem, qwm = check_quality(floor, None, None, "2026-11-17", monitor=True)
ok("게이트: monitor에서 floor → error 없음", not any("BODY-TOTAL" in e for e in _qem))
ok("게이트: monitor에서 floor → warning", any("밀도 부족" in w for w in qwm))
_qed, qwd = check_quality(dense, None, None, "2026-11-17", attempt=1, attempts_total=3)
ok("게이트: dense → BODY-TOTAL error 없음", not any("BODY-TOTAL" in e for e in _qed))
ok("게이트: dense → 밀도 warning 없음", not any("밀도" in w for w in qwd))
# attempt=1인데 attempts_total=1이면 최종이므로 완화 판정 (단일 시도 모드)
_qe1, _ = check_quality(thin, None, None, "2026-11-17", attempt=1, attempts_total=1)
ok("게이트: attempts_total=1이면 최종 의미", not any("BODY-TOTAL" in e for e in _qe1))

# --- 7. CLI 통합: --attempt 인자 ---
# check_quality만 보는 게이트 테스트와 달리 CLI는 구조 게이트(check)까지
# 태우므로, briefing/keynums/timeline/analysis 최소 개수를 갖춘 이슈를 쓴다.
def _cli_issue(body):
    iss = _issue(body, n_sources=3)
    iss["briefing"] = [
        {"id": "a", "headline": "OpenAI 새 모델 공개", "summary": "요약입니다."},
        {"id": "b", "headline": "Anthropic 새 기능 공개", "summary": "요약입니다."},
        {"id": "c", "headline": "Google 새 모델 공개", "summary": "요약입니다."},
    ]
    iss["keynums"] = [
        {"val": "30%", "lab": "가격 인하", "sub": "OpenAI 발표"},
        {"val": "2배", "lab": "응답 속도", "sub": "OpenAI 발표"},
        {"val": "100개", "lab": "과제 묶음", "sub": "OpenAI 발표"},
    ]
    iss["timeline"] = [
        {"t": "11/17 09:00", "d": "모델 공개"},
        {"t": "11/17 10:00", "d": "문서 공개"},
        {"t": "11/17 11:00", "d": "API 적용"},
    ]
    import copy as _copy
    _b = _copy.deepcopy(iss["analysis"][0])
    _b["id"] = "b"
    _b["title"] = "2. Anthropic 새 기능"
    _b["takeaway"] = ("가격이 내려도 호출량이 늘면 총비용은 달라집니다. "
                      "적용 전에 자기 사용량을 먼저 재고 나서 도입을 결정하면 됩니다.")
    iss["analysis"].append(_b)
    return iss


_here = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    _f = Path(td) / "2026-11-17.json"
    _cli = _cli_issue(_thin_body)
    ok("CLI 픽스처: 시사점 2문장·60자 이상",
       len(_cli["analysis"][0]["takeaway"]) >= 60 and len(_cli["analysis"][1]["takeaway"]) >= 60)
    _f.write_text(json.dumps(_cli, ensure_ascii=False), encoding="utf-8")
    r1 = subprocess.run([sys.executable, str(_here / "validate.py"), "--date", "2026-11-17",
                         "--attempt", "1", str(_f)], capture_output=True, text=True)
    ok("CLI: --attempt 1 → exit 1 (BODY-TOTAL error)", r1.returncode == 1 and "BODY-TOTAL" in r1.stdout)
    r3 = subprocess.run([sys.executable, str(_here / "validate.py"), "--date", "2026-11-17",
                         "--attempt", "3", str(_f)], capture_output=True, text=True)
    ok("CLI: --attempt 3 → exit 0 (warning만)", r3.returncode == 0)
    rm = subprocess.run([sys.executable, str(_here / "validate.py"), "--date", "2026-11-17",
                         "--monitor", str(_f)], capture_output=True, text=True)
    ok("CLI: --monitor → exit 0 (과거 호 보호)", rm.returncode == 0)

print(f"\nP23: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
