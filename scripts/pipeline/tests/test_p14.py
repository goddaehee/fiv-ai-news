#!/usr/bin/env python3
"""P14 회귀 테스트: 분석 밀도 개선.

배경 (벤치마킹 패널 실측, 원본 fiv.co.kr 2026-10-21호 vs 클론 10/22·10/23호):
- 분석 4~5개 vs 원본 7개 → select MAX_MAIN 5→7, 프롬프트 "main_topics 전부 1:1"
- 본문 ~340자 vs 원본 ~750자 → 프롬프트 본문 합계 500자+·문단당 140자 안팎,
  게이트는 warning으로 가시화만 (hard 게이트는 결호 위험 — P9 교훈)
- P23 (5차 평가 P5): 500자 기준으로는 평균 391자에 머물러 프롬프트를
  700자 목표·문단당 200~250자·3문단 역할 재배정으로 상향하고, BODY-TOTAL
  attempt-aware 2단계 게이트(최종 전 error·최종은 500자 하한만 error)로
  피드백 수렴을 붙인다. 재료는 summary 절단 180→450자로 확장.
- 출처 1.8개 vs 원본 4.7개 → 프롬프트 기본 3개, attach_sources 상한 2→4,
  payload 버킷 아이템 3→5개
- 오타 게이트 부재 ("Open아AI" 발행) → TYPO-001: U+FFFD + 영문-한글-영문
  혼합 패턴을 error로 차단하고 재시도 피드백에 연결
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import attach_sources, render_feedback, PROMPT
from select_items import MAX_MAIN, select_buckets
from validate import check_quality, check_typo, collect_structured_errors

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# --- 1. 선별 상한: MAX_MAIN 7 ---
ok("MAX_MAIN == 7", MAX_MAIN == 7)

from datetime import datetime, timezone, timedelta
_NOW = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _scored(name, url, source):
    items = [{"title": f"OpenAI GPT 발표 {name}", "summary": "성능이 30% 향상됨",
              "url": url, "source": source, "published": _NOW}]
    return (name, items)


_many = [_scored(f"t{i}", f"https://dom{i}.com/a", f"소스{i}") for i in range(9)]
main, rest = select_buckets(_many)
ok("서로 다른 도메인 9개 → main 7개", len(main) == 7 and len(rest) == 2)


# --- 2. 프롬프트 밀도 요구 (P23: 500자+ → 700자 목표·600자 미달) ---
ok("프롬프트: analysis briefing 상위 1:1 + 개수 하한", "analysis는 briefing 상위 5~7개의 id와 1:1" in PROMPT and "최소 5개" in PROMPT)
ok("프롬프트: 본문 합계 700자 목표·600자 미만 미달", "기사당 본문 합계 700자 목표·600자 미만이면 미달" in PROMPT)
ok("프롬프트: 문단당 200~250자·3문단", "body 3문단(문단당 2~3문장, 200~250자" in PROMPT)
ok("프롬프트: 500자 기준 잔재 없음", "본문 합계 500자 이상" not in PROMPT)
ok("프롬프트: 출처는 그 이야기의 아이템만 (P16 — 3개 패딩 금지)", "바로 그 이야기의 아이템에서만" in PROMPT and "3개 기본" not in PROMPT)
ok("프롬프트: 본문 구성 지침", "본문 구성: 첫 문단=무슨 일인가" in PROMPT)
ok("프롬프트: 문단 역할 재배정 (측정 조건)", "회사 발표 수치와 그 측정 조건" in PROMPT)
ok("프롬프트: 자기 검수 지시", "출력 전에 기사마다 본문 글자 수를 셉니다" in PROMPT)
ok("프롬프트: 지어내기 금지 재강조", "지어내면 호가 폐기됩니다" in PROMPT)


# --- 3. attach_sources 상한 4 ---
SNAP = {"items": [
    {"title": f"기사 {i}", "url": f"https://media{i}.com/a{i}", "source": f"매체{i}",
     "kind": "doc", "summary": f"요약 {i} 수치 30% 포함", "published": _NOW}
    for i in range(5)
]}
_issue = {"analysis": [{
    "id": "x",
    "sources": [{"url": f"https://media{i}.com/a{i}"} for i in range(5)],
}]}
out = attach_sources(_issue, SNAP)
ok("attach_sources: 5개 요청 → 4개까지 재조립", len(out["analysis"][0]["sources"]) == 4)
_issue2 = {"analysis": [{
    "id": "x",
    "sources": [{"url": "https://media0.com/a0"}, {"url": "https://media1.com/a1"}],
}]}
out2 = attach_sources(_issue2, SNAP)
ok("attach_sources: 2개 요청은 그대로 2개", len(out2["analysis"][0]["sources"]) == 2)


# --- 4. TYPO-001 게이트 ---
def _base_issue():
    return {
        "date": "2026-10-24", "title": "제목", "heroline": "h", "dek": "d",
        "tag": "AI", "briefMin": 5, "readMin": 10,
        "briefing": [{"id": "a", "headline": "OpenAI 새 모델 공개", "summary": "요약입니다."}],
        "keywords": ["OpenAI"], "mainEvent": "OpenAI 새 모델 공개 행사",
        "keynums": [{"val": "30%", "lab": "성능 향상", "sub": "OpenAI 발표"}],
        "timeline": [{"t": "10/24 09:00", "d": "모델 공개"}],
        "intro": "10월 24일 토요일 발행. 오늘의 소식입니다.",
        "analysis": [{
            "id": "a", "title": "1. OpenAI 새 모델", "bullets": ["핵심 사실 하나", "둘째 사실"],
            "body": [
                # P23: 정상 호 본문은 600자 이상으로 유지한다 (BODY-TOTAL이
                # 최종 attempt 의미의 기본 호출에서도 error를 내지 않게).
                "OpenAI가 새 모델을 공개했습니다. 응답 속도는 2배 빨라지고 가격은 30% 내렸습니다. 새 모델은 기존 모델과 같은 방식으로 호출할 수 있고, 문서도 같은 날 함께 열렸습니다. 회사는 이번 공개를 개발자 대상 행사에서 발표했으며, 적용 대상은 이용자 전체라고 밝혔습니다. 기존 모델을 쓰던 이용자는 설정을 바꾸지 않고도 새 모델을 선택할 수 있습니다.",
                "이전 모델과 비교하면 생성 속도가 크게 올랐고, 이번 수치는 회사가 공개한 과제 100개로 잰 평균값입니다. 과제 묶음은 영어 과제로 구성돼 있고, 긴 문서 과제나 다른 언어 과제는 포함되지 않았습니다. 응답 속도와 가격 인하는 같은 과제 묶음에서 나온 값이라 실제 업무 조건과는 다를 수 있습니다.",
                "다만 평가는 영어 과제뿐이라 다른 언어에서는 확인되지 않았고, 가격은 API 호출 기준이라 구독 요금과는 다릅니다. 외부 독립 측정은 아직 공개되지 않았고, 회사가 밝힌 수치만으로 실제 효과를 단정할 수는 없습니다. 도입을 검토하는 쪽은 영어 외 과제 점수와 실제 호출량을 함께 확인하면 됩니다.",
            ],
            "takeaway": "속도가 바뀐 점이 중요합니다. 적용 전에 자기 과제 점수부터 확인하면 됩니다.",
            "tags": ["OpenAI"], "sources": [{"handle": "OpenAI", "url": "https://openai.com/a", "kind": "doc"}],
        }],
        "mood": {"shift": "s", "grow": "g", "caution": "c", "heat": "h"},
        "tips": [{"title": "팁 제목", "body": "팁 본문입니다.", "via": "OpenAI"}],
        "method": "m",
    }


ok("정상 호: 오타 검출 없음", check_typo(_base_issue()) == [])

bad = _base_issue()
bad["analysis"][0]["body"] = ["Open아AI가 새 모델을 공개했습니다. 성능이 30% 올랐습니다. 배경 설명이 이어집니다. 수치 조건도 함께 적습니다."]
errs = check_typo(bad)
ok("혼합 오타 'Open아AI' 검출", any("TYPO-001" in e and "Open아AI" in e for e in errs))

bad2 = _base_issue()
bad2["briefing"][0]["headline"] = "깨진�제목"
ok("U+FFFD 검출", any("TYPO-001" in e for e in check_typo(bad2)))

qerr, _qwarn = check_quality(_base_issue(), None, None, "2026-10-24")
ok("정상 호: check_quality error 없음", not qerr)
qerr2, _ = check_quality(bad, None, None, "2026-10-24")
ok("오타 호: check_quality가 TYPO-001 error", any("TYPO-001" in e for e in qerr2))

# 구조화 에러 + 피드백 렌더링
serr = collect_structured_errors(bad, None)
typo_entries = [e for e in serr if e.get("code") == "TYPO-001"]
ok("collect_structured_errors에 TYPO-001 포함",
   len(typo_entries) == 1 and "Open아AI" in typo_entries[0]["token"])
import json as _json
import tempfile as _tf
with _tf.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    _json.dump({"errors": typo_entries}, f, ensure_ascii=False)
    _sidecar = f.name
fb = render_feedback(_sidecar)
ok("render_feedback: TYPO-001 처방 렌더링", "TYPO-001" not in fb and "Open아AI" in fb and "고쳐 쓰세요" in fb)


# --- 5. 밀도 게이트 — P23 attempt-aware BODY-TOTAL (2단계) ---
# 기본 호출(attempt 미지정)은 최종 attempt 의미: 600자 미만은 warning,
# 500자 미만만 error. 최종 전 attempt에서는 600자 미만도 error.
thin = _base_issue()
thin["analysis"][0]["body"] = ["가" * 260, "나" * 260]  # 합계 521자
_qe, qw = check_quality(thin, None, None, "2026-10-24", attempt=1, attempts_total=3)
ok("BODY-TOTAL: 최종 전 attempt에서 600자 미만 → error",
   any("BODY-TOTAL" in e for e in _qe))
_qe3, qw3 = check_quality(thin, None, None, "2026-10-24", attempt=3, attempts_total=3)
ok("BODY-TOTAL: 최종 attempt에서 500자 이상이면 error 없음", not any("BODY-TOTAL" in e for e in _qe3))
ok("BODY-TOTAL: 최종 attempt에서 600자 미만 → 밀도 warning", any("밀도 부족" in w for w in qw3))
_qe0, qw0 = check_quality(thin, None, None, "2026-10-24")
ok("BODY-TOTAL: attempt 미지정은 최종 의미 (error 없음)", not any("BODY-TOTAL" in e for e in _qe0))

floor = _base_issue()
floor["analysis"][0]["body"] = ["가" * 200, "나" * 200]  # 합계 401자
_qef, _ = check_quality(floor, None, None, "2026-10-24", attempt=3, attempts_total=3)
ok("BODY-TOTAL: 최종 attempt에서도 500자 미만은 error", any("BODY-TOTAL" in e for e in _qef))
_qem, qwm = check_quality(floor, None, None, "2026-10-24", monitor=True)
ok("BODY-TOTAL: monitor 모드에서는 error 없음 (과거 호 보호)", not any("BODY-TOTAL" in e for e in _qem))
ok("BODY-TOTAL: monitor 모드에서도 밀도 warning은 남음", any("밀도 부족" in w for w in qwm))

short = _base_issue()
_qe, qw = check_quality(short, None, None, "2026-10-24")
ok("출처 3개 미만 → 출처 밀도 warning", any("출처 밀도 부족" in w for w in qw))

dense = _base_issue()
dense["analysis"][0]["body"] = ["가" * 310, "나" * 310]  # 합계 621자
dense["analysis"][0]["sources"] = [
    {"handle": "A", "url": "https://openai.com/a", "kind": "doc"},
    {"handle": "B", "url": "https://anthropic.com/b", "kind": "doc"},
    {"handle": "C", "url": "https://google.com/c", "kind": "doc"},
]
_qe3, qw3 = check_quality(dense, None, None, "2026-10-24", attempt=1, attempts_total=3)
ok("밀도 충족 시 BODY-TOTAL error·밀도 warning 없음",
   not any("BODY-TOTAL" in e for e in _qe3) and not any("밀도" in w for w in qw3))

print(f"\nP14: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
