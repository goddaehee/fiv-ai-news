#!/usr/bin/env python3
"""P29 회귀 테스트: 단독 출처 버킷의 메인 진입 문턱 상향.

실측 배경 (2026-11-22·11-23호): 분석당 출처 평균 2.00 < 2.5 목표.
두 호 모두 6개 분석 중 3개가 출처 1개였다. 프롬프트는 이미
"가능하면 2~3개, 아이템이 1개뿐이면 1개만"이라서 LLM이 늘릴 수 없고,
선별 단계에서 교차보도 없는 이야기가 메인을 차지한 것이 원인이다.
→ select_buckets: 단독 출처(커버리지 1) 버킷은 6점 이상이어야 메인,
교차보도(커버리지 2+) 버킷은 기존 5점 유지. 탈락분은 단신(rest)으로
남아 브리핑에서 다룰 수 있다. 얇은 날 MIN_MAIN(3) 바닥은 문턱을
풀고 채운다 (P15 하한 유지).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from select_items import (
    MIN_MAIN,
    SCORE_CUTOFF,
    SINGLE_SOURCE_CUTOFF,
    _main_cutoff,
    select_buckets,
)

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


_NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _it(title, source, url, summary=""):
    return {"title": title, "source": source, "url": url,
            "summary": summary, "published": _NOW}


def _single5(name, domain, label):
    # 단독 출처·5점: 신선도 2 + 관련성 2(숫자+고유명사) + 근거 1(비공식 URL)
    return (name, [_it(f"OpenAI GPT 발표 {name} 30% 개선", label,
                       f"https://{domain}/x", "성능이 30% 향상됨")])


def _single6(name, domain, label):
    # 단독 출처·6점: 위와 같되 공식 URL이라 근거 2점
    return (name, [_it(f"OpenAI GPT 발표 {name} 30% 개선", label,
                       f"https://{domain}/x", "성능이 30% 향상됨")])


def _multi5(name, first_domain, label):
    # 교차보도 2개 매체·5점: 영향도 1 + 신선도 2 + 관련성 0 + 근거 2(공식 포함)
    return (name, [
        _it("새 모델 출시 소식", label, f"https://{first_domain}/a", "모델이 공개됐다"),
        _it("새 모델 출시 후속", "Wire", "https://openai.com/b", "후속 요약"),
    ])


# --- 1. 문턱 값 ---
ok("단독 출처 문턱은 6점", _main_cutoff(_single5("t", "zdnet.com", "L")[1]) == 6)
ok("교차보도 문턱은 5점 유지",
   _main_cutoff(_multi5("t", "techcrunch.com", "L")[1]) == 5)
ok("SINGLE_SOURCE_CUTOFF == SCORE_CUTOFF + 1",
   SINGLE_SOURCE_CUTOFF == SCORE_CUTOFF + 1)

# --- 2. 11-23호 재현: 교차보도 5개 + 단독 5점 2개 + 단독 6점 1개 ---
ranked = [
    _multi5("m1", "techcrunch.com", "L1"),
    _multi5("m2", "theverge.com", "L2"),
    _multi5("m3", "arstechnica.com", "L3"),
    _multi5("m4", "bleepingcomputer.com", "L4"),
    _multi5("m5", "reuters.com", "L5"),
    _single5("s5a", "zdnet.com", "L6"),
    _single5("s5b", "wired.com", "L7"),
    _single6("s6", "openai.com", "L8"),
]
main, rest = select_buckets(ranked)
main_names = {m[0] for m in main}
rest_names = {r[0] for r in rest}
ok("교차보도 5개 전부 메인", all(f"m{i}" in main_names for i in range(1, 6)))
ok("단독 6점(공식 발표)은 메인 유지", "s6" in main_names)
ok("단독 5점 2개는 메인에서 제외", "s5a" not in main_names and "s5b" not in main_names)
ok("단독 5점 2개는 단신(rest)에 남음", "s5a" in rest_names and "s5b" in rest_names)
ok("메인 6개·단신 2개", len(main) == 6 and len(rest) == 2)

# --- 3. 얇은 날: 단독 5점만 3개면 MIN_MAIN 바닥은 문턱을 풀고 채운다 ---
thin = [
    _single5("t1", "zdnet.com", "L1"),
    _single5("t2", "wired.com", "L2"),
    _single5("t3", "theregister.com", "L3"),
]
main, rest = select_buckets(thin)
ok("얇은 날 MIN_MAIN까지 채워짐", len(main) == MIN_MAIN)
ok("얇은 날 단신 없음", len(rest) == 0)

print(f"P29 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
