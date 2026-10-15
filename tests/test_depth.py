#!/usr/bin/env python3
"""2주차: 깊이 슬롯 게이트 + 근거 연결 + 문체 패스 테스트."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "pipeline"))
from validate import check_depth


def good_analysis():
    return {
        "id": "test-1",
        "title": "1. 테스트 기사",
        "bullets": ["핵심 요약 1", "핵심 요약 2", "핵심 요약 3"],
        "body": [
            "OpenAI가 GPT-6을 공개했다. 추론 속도가 50% 빨라졌고 가격은 30% 낮아졌다.",
            "이번 발표는 지난 3개월의 모델 경쟁 맥락에서 나왔다. Anthropic과 Google도 비슷한 시기에 신모델을 냈다.",
            "다만 벤치마크는 회사 자체 측정이라 독립 검증이 필요하다. 아직 실제 사용 후기는 부족하다.",
        ],
        "takeaway": "이번 발표는 모델 경쟁에서 중요한 전환점이다. 가격 인하가 실무 도입에 영향을 줄 것이다.",
        "sources": [{"handle": "OpenAI News", "url": "https://openai.com/news/x", "kind": "doc"}],
    }


def test_all_slots():
    errors, _ = check_depth({"analysis": [good_analysis()]})
    assert not errors, errors
    print("ok: all slots filled")


def test_missing_two_slots():
    a = good_analysis()
    a["body"] = ["짧은 문단."]
    a["takeaway"] = ""
    errors, _ = check_depth({"analysis": [a]})
    assert any("depth" in e for e in errors), errors
    print("ok: 2+ missing slots = error")


def test_missing_one_slot_warning():
    a = good_analysis()
    a["body"] = a["body"][:2]  # limits 슬롯 제거 (3번째 문단 삭제)
    a["body"][1] += " 한계는 아직 불확실하다."  # limits는 유지
    # context는 유지 (2문단), numbers 유지, what 유지, why 유지
    errors, warnings = check_depth({"analysis": [a]})
    assert not errors, errors
    print("ok: 1 missing slot = warning only (or none)")


def test_avg_omission_rate():
    # 2개 기사, 각 2개 슬롯 미충족 → 4개 > 허용 2개 = error
    # P1 (Claude C-3): 임계값이 비율(10%)에서 절대개수(max(2, ceil(슬롯×0.10)))로 변경
    a1 = good_analysis()
    a1["body"] = ["짧은 문단."]
    a1["takeaway"] = ""
    a2 = good_analysis()
    a2["body"] = ["짧은 문단."]
    a2["takeaway"] = ""
    errors, _ = check_depth({"analysis": [a1, a2]})
    assert any("전체 슬롯 생략" in e for e in errors), errors
    print("ok: avg omission > allowed = error")


def test_no_sources_with_numbers():
    a = good_analysis()
    a["sources"] = []
    _, warnings = check_depth({"analysis": [a]})
    assert any("evidence" in w for w in warnings), warnings
    print("ok: numbers without sources = warning")


def test_distinct3_threshold():
    # 0.869 임계값 고정 (0주차 원본 실측 0.919 - 5%p)
    # 반복 문장이 많은 기사는 warning
    rep = " ".join(["같은 문장 반복입니다."] * 30)
    a = good_analysis()
    a["body"] = [rep, rep, rep]
    a["takeaway"] = "중요한 내용입니다. " * 10
    _, warnings = check_depth({"analysis": [a]})
    assert any("distinct-3" in w for w in warnings), warnings
    print("ok: distinct-3 threshold 0.869")


if __name__ == "__main__":
    test_all_slots()
    test_missing_two_slots()
    test_missing_one_slot_warning()
    test_avg_omission_rate()
    test_no_sources_with_numbers()
    test_distinct3_threshold()
    print("2주차 tests passed")
