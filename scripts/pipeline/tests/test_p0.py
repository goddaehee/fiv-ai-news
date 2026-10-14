#!/usr/bin/env python3
"""P0 회귀 테스트: validate 8종 검사 + thicken_take/body 템플릿 제거."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import check_p0, _normalize_sim, _overlap, _jaccard
from draft import thicken_take, thicken_body

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def base_issue(**kw):
    issue = {
        "date": "2026-10-14",
        "mainEvent": "AI 실행력 보고서",
        "briefing": [
            {"id": "a1", "headline": "A가 B를 했다", "summary": "A가 B를 하면서 시장이 바뀌고 있다"},
        ],
        "analysis": [
            {
                "id": "a1",
                "title": "A가 B를 했다",
                "bullets": ["불릿1", "불릿2"],
                "body": ["첫 번째 문단입니다. 내용이 충분합니다.", "두 번째 문단입니다. 여기도 충분합니다."],
                "takeaway": "A의 B는 시장에 영향을 줍니다. 담당자는 이번 주 안에 검토하면 됩니다.",
                "tags": ["AI", "시장"],
                "sources": [],
            }
        ],
        "tips": [{"title": "팁 제목", "body": "팁 본문 내용입니다. 다릅니다.", "via": "공식 블로그"}],
    }
    issue.update(kw)
    return issue


# --- TPL-001 ---
ok("TPL-001 탐지", any("TPL-001" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0],
        "takeaway": "A은 오늘 확인할 변경입니다. 숫자·적용 범위·분모는 출처 문서에서 다시 보고."}]), None)[0]))
ok("TPL-001 정상 통과", not check_p0(base_issue(), None)[0])

# --- ID-001 ---
ok("ID-001 탐지", any("ID-001" in e for e in check_p0(
    base_issue(mainEvent="a1"), None)[0]))
ok("ID-001 정상 통과", not any("ID-001" in e for e in check_p0(base_issue(), None)[0]))

# --- DUP-001 ---
ok("DUP-001 탐지", any("DUP-001" in e for e in check_p0(
    base_issue(briefing=[{"id": "a1", "headline": "엔비디아가 새로운 AI 칩을 발표했다", "summary": "엔비디아가 새로운 AI 칩을 발표했다"}]), None)[0]))
ok("DUP-001 정상 통과", not any("DUP-001" in e for e in check_p0(base_issue(), None)[0]))

# --- ID-002 ---
ok("ID-002 탐지", any("ID-002" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "tags": ["a1"]}]), None)[0]))
ok("ID-002 빈태그 탐지", any("ID-002" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "tags": [" "]}]), None)[0]))

# --- DUP-002 ---
ok("DUP-002 탐지", any("DUP-002" in e for e in check_p0(
    base_issue(tips=[{"title": "초안 숫자는 공식 페이지에서 다시 봅니다", "body": "초안 숫자는 공식 페이지에서 다시 봅니다", "via": "블로그"}]), None)[0]))

# --- VIA-001 ---
ok("VIA-001 탐지", any("VIA-001" in e for e in check_p0(
    base_issue(tips=[{"title": "t", "body": "b", "via": "파이프라인"}]), None)[0]))
ok("VIA-001 빈값 탐지", any("VIA-001" in e for e in check_p0(
    base_issue(tips=[{"title": "t", "body": "b", "via": ""}]), None)[0]))

# --- thicken_take: 템플릿 생성 금지 ---
ok("thicken_take 템플릿 없음", "오늘 확인할 변경입니다" not in thicken_take("", ["불릿"], "제목"))
ok("thicken_take 미달은 빈값", thicken_take("짧음", ["불릿"], "제목") == "")
good_take = "엔비디아의 새 AI 칩 발표는 데이터센터 시장에 직접 영향을 줍니다. 인프라 담당자는 이번 분기 안에 도입 타당성을 검토하면 됩니다. 추가로 가격 정책도 함께 확인합니다."
ok("thicken_take 정상 유지", thicken_take(good_take, ["불릿"], "제목") == good_take)

# --- thicken_body: 패딩 없음 ---
ok("thicken_body 패딩 없음", "조건과 분모는" not in " ".join(thicken_body(["짧은 본문"], ["불릿1"])))

# --- EMPTY-001/002 ---
ok("EMPTY-001 탐지", any("EMPTY-001" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "takeaway": ""}]), None)[0]))
ok("EMPTY-002 탐지", any("EMPTY-002" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "body": []}]), None)[0]))

# --- 오탐 방지: 정상 콘텐츠 ---
clean = {
    "mainEvent": "AI 에이전트 경쟁 심화",
    "briefing": [
        {"id": "b1", "headline": "엔비디아가 새로운 AI 칩을 발표했다",
         "summary": "데이터센터용 차세대 칩 공개. 전력 효율이 2배 개선됐다."},
    ],
    "analysis": [{
        "title": "엔비디아 신형 칩 분석",
        "body": ["첫 번째 문단입니다. 전력 효율 개선이 핵심입니다.", "두 번째 문단입니다. 가격은 아직 공개되지 않았습니다."],
        "takeaway": "신형 칩은 데이터센터 비용을 낮춥니다. 인프라 팀은 이번 분기 도입을 검토하면 됩니다.",
        "tags": ["AI", "반도체", "엔비디아"],
    }],
    "tips": [{"title": "GPU 비용 절감 팁", "body": "스팟 인스턴스를 활용하면 비용을 70% 줄일 수 있습니다.", "via": "AWS 블로그"}],
}
ce, cw = check_p0(clean, None)
ok("정상 콘텐츠 오탐 없음", not ce)

# --- 유사도 함수 ---
ok("overlap 포함관계", _overlap(_normalize_sim("엔비디아가 새로운 AI 칩을 발표했다"), _normalize_sim("엔비디아가 새로운 AI 칩을 발표했다 추가")) > 0.8)
ok("jaccard 다름", _jaccard(_normalize_sim("완전히 다른 문장입니다"), _normalize_sim("전혀 겹치지 않는 내용")) < 0.3)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
