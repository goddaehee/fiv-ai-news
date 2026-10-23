#!/usr/bin/env python3
"""P12 회귀 테스트: keynums 깨진 데이터 노출 방지.

1. 의미 검증 게이트 (KEYNUMS-SEMANTIC) — 피드명 lab·내부 문자열 sub 차단
2. 폴백(_fallback_keynum)은 유효 항목만 생성 — 만들 수 없으면 충원 안 함
3. 정상 keynum은 통과 (NUM_RE 밖 단위 '125건'·'2조 달러' 포함)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import check_keynums_semantics
from draft import _fallback_keynum

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _sem(issue):
    bag: list[str] = []
    check_keynums_semantics(issue, bag)
    return bag


def test_gate_blocks_feedname_lab():
    issue = {"keynums": [
        {"val": "$5", "lab": "Anthropic GNews", "sub": "수집 요약"},
        {"val": "50%", "lab": "평가 어려움 응답 비율", "sub": "신규 설문"},
        {"val": "77%", "lab": "추론 비용 절감", "sub": "사례 보고"},
    ]}
    bag = _sem(issue)
    ok("피드명 lab 차단", any("KEYNUMS-SEMANTIC" in e and "lab" in e for e in bag))
    ok("내부 문자열 sub 차단", any("KEYNUMS-SEMANTIC" in e and "sub" in e for e in bag))
    ok("깨진 항목 1개만 지목", sum(1 for e in bag if "[0]" in e) == 2 and len(bag) == 2)


def test_gate_blocks_nonnumeric_val():
    issue = {"keynums": [
        {"val": "법률", "lab": "법률 개정", "sub": "공식 발표"},
        {"val": "50%", "lab": "응답 비율", "sub": "설문"},
        {"val": "77%", "lab": "비용 절감", "sub": "사례"},
    ]}
    bag = _sem(issue)
    ok("숫자 없는 val 차단", any("val에 숫자" in e for e in bag))


def test_gate_passes_valid():
    issue = {"keynums": [
        {"val": "125건", "lab": "신규 공개 모델 수", "sub": "허깅페이스 집계"},
        {"val": "2조 달러", "lab": "AI 인프라 투자 규모", "sub": "블룸버그 보도"},
        {"val": "128GB", "lab": "단일 GPU 메모리", "sub": "엔비디아 발표"},
        {"val": "$15B", "lab": "기업 가치 평가액", "sub": "테크크런치 보도"},
    ]}
    bag = _sem(issue)
    ok("정상 keynum 통과 (NUM_RE 밖 단위 포함)", bag == [])


def test_gate_blocks_domain_only_lab():
    issue = {"keynums": [
        {"val": "50%", "lab": "reuters.com", "sub": "보도"},
        {"val": "50%", "lab": "응답 비율", "sub": "설문"},
        {"val": "77%", "lab": "비용 절감", "sub": "사례"},
    ]}
    bag = _sem(issue)
    ok("도메인뿐인 lab 차단", any("도메인뿐" in e for e in bag))


def _item(title, source="Google News AI", origin="https://www.reuters.com/"):
    it = {"title": title, "summary": "", "source": source, "url": "https://news.google.com/rss/articles/x"}
    if origin:
        it["origin_url"] = origin
    return it


def test_fallback_creates_valid():
    it = _item("Anthropic 기업가치 $15B 돌파, 투자 유치 확대")
    fb = _fallback_keynum(it, set())
    ok("폴백 유효 항목 생성", fb is not None)
    if fb:
        ok("폴백 lab은 설명 (피드명 아님)", "GNews" not in fb["lab"] and "수집" not in fb["lab"])
        ok("폴백 sub은 발행처 도메인", fb["sub"] == "reuters.com")
        ok("폴백 항목이 게이트 통과", _sem({"keynums": [fb]}) == [])


def test_fallback_skips_when_no_origin():
    it = _item("Anthropic 기업가치 $15B 돌파", origin=None)
    ok("origin_url 없으면 충원 안 함", _fallback_keynum(it, set()) is None)


def test_fallback_skips_when_val_not_in_title_surface():
    # 정규화 후 표면($15 billion)과 원문 표면이 다르면 lab을 만들 수 없다 → 스킵
    it = _item("Anthropic raises at $15 billion valuation")
    fb = _fallback_keynum(it, set())
    if fb is not None:
        ok("표면 불일치 시에도 lab은 내부 문자열 아님", "수집" not in fb["lab"])


def test_fallback_skips_dup_val():
    it = _item("Anthropic 기업가치 $15B 돌파")
    ok("이미 있는 val은 충원 안 함", _fallback_keynum(it, {"$15B"}) is None)


def main():
    test_gate_blocks_feedname_lab()
    test_gate_blocks_nonnumeric_val()
    test_gate_passes_valid()
    test_gate_blocks_domain_only_lab()
    test_fallback_creates_valid()
    test_fallback_skips_when_no_origin()
    test_fallback_skips_when_val_not_in_title_surface()
    test_fallback_skips_dup_val()
    print(f"P12: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
