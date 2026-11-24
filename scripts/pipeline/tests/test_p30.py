#!/usr/bin/env python3
"""P30 회귀 테스트: 한자 혼입 게이트 (TYPO-001 확장).

배경 (6차 벤치마킹 평가, 2026-11-24):
- 생성 모델이 중국어 단어를 한글 문장에 섞어 낸 결함이 실제 발행본에서
  2회 확인됐다 — 2026-09-29호 "공개한节奏가 포인트입니다",
  2026-11-23호 "봇넷이 어떤 경로로 재集结했는지".
- 발행본 전수(60호) 한자 전수 조사: 위 2건 외에는 한국어 기사 제목의
  관용 약어뿐 — 美(미국, 2건), 立法(입법, 1건). 이 3자만 허용하면
  전수 기준 오탐 0건으로 결함 2건을 모두 잡는다.
- 게이트는 기존 TYPO-001 코드를 그대로 쓴다 (재시도 피드백 연결 유지).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import _typo_findings, check_typo, collect_structured_errors

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _issue(body_text: str) -> dict:
    return {
        "title": "테스트 호",
        "analysis": [{
            "id": "a1", "title": "기사 제목", "bullets": ["요약 한 줄"],
            "body": [body_text], "takeaway": "시사점입니다. 확인하면 됩니다.",
            "tags": [], "sources": [{"url": "https://example.org/x"}],
        }],
    }


# --- 1. 실제 결함 2건이 잡힌다 ---
f = _typo_findings(_issue("봇넷이 어떤 경로로 재集结했는지에 대한 구체적 분석은 담겨 있지 않습니다."))
ok("集结 혼입 검출", any("集结" in x["token"] for x in f))

f = _typo_findings(_issue("25일 라이브 아바타를 붙여 공개한节奏가 포인트입니다."))
ok("节奏 혼입 검출", any("节奏" in x["token"] for x in f))

# --- 2. 관용 약어는 통과한다 (발행본 전수 오탐 0건 기준) ---
ok("美 약어 허용", _typo_findings(_issue("美 재무장관이 엔비디아 GPU 판매 책임론을 제기했습니다.")) == [])
ok("立法 약어 허용", _typo_findings(_issue("아동 대상 챗봇 행위 금지立法 시행 보도입니다.")) == [])
ok("순수 한글 문장 통과", _typo_findings(_issue("미국 재무장관이 입법 일정을 밝혔습니다.")) == [])

# --- 3. 허용 약어와 섞여 있어도 비허용 한자가 있으면 잡는다 ---
f = _typo_findings(_issue("美 재무장관 발언 뒤 시장节奏가 빨라졌습니다."))
ok("허용+비허용 혼합 시 검출", any("节奏" in x["token"] for x in f))

# --- 4. 게이트·구조화 에러 연결 ---
errs = check_typo(_issue("다시 재集结한 정황이 포착됐습니다."))
ok("check_typo가 TYPO-001 error 반환", any("TYPO-001" in e for e in errs))

structured = collect_structured_errors(_issue("다시 재集结한 정황이 포착됐습니다."), {})
ok("구조화 에러에 TYPO-001 포함", any(e.get("code") == "TYPO-001" for e in structured))

print(f"P30: PASS {PASS} / FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
