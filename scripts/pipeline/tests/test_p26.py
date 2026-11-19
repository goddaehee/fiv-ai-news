#!/usr/bin/env python3
"""P26 회귀 테스트: 2026-11-19호 — 분수 오탐 + 허용 집합 범위 + 복원력.

실측 실패 원인 (run 44452750638 등):
1. 분수 오탐 "4분" — 본문 "4분의 1을 넘는 28%"의 "분"이 분(시간) 단위로
   추출돼 NUMBERS-UNGROUNDED로 차단됐다. 11/03호 "3분기"→"3분" 오탐과
   같은 계열이다.
   → 수치 추출 전에 "N분의 M" 분수 표현을 마스킹한다. 실제 "4분"(시간)은
   그대로 차단돼야 한다.
2. 허용 집합 범위 — analysis 출처에 없는 교차보도 아이템의 수치가 본문에
   정확히 번역돼도 차단됐다 ($81.3 Billion → 813억, $400 Billion →
   4000억). MUST-COVER 톱스토리 아이템이 출처에서 빠진 것이 근원이다.
   → 허용 집합을 같은 스토리 그룹의 수집 아이템까지 넓히고,
   attach_sources가 MUST-COVER 아이템을 반드시 붙이도록 보강한다.
3. 복원력 — JSON 파싱 실패가 attempt를 rc=1 크래시로 통째로 소모했고,
   LLM 타임아웃은 마지막 attempt에서 여유 없이 끝났다.
   → 같은 attempt 내 JSON 재수리 + 타임아웃 시 보너스 1 attempt.

3번 항목(본문 밀도 결정적 보강)은 범위 조정됨: PR #122(문장 수 2~3→4~6)
머지 뒤 11/19호 재실행에서 본문 평균 879자(810~938자, 목표 600 초과)가
실측돼 프롬프트만으로 수렴한다는 전제가 깨졌다. 불릿 병합은 구현하지
않고, PR #122 효과 확인으로 갈음한다.

P26b (Gemini 1석 재리뷰 CONDITIONAL PASS 후속, 2026-11-19):
- MUST-COVER 보강의 게이트 우회 — fail-open 중화 + 부착 bar 상향
  (본문 겹침 2개 이상, 또는 1개 + 제목 토큰 공유) + 차순위 순회.
- 스토리 그룹 확장 오염 — 확장용 엄격 기준(자체 출처와 제목 토큰
  3개 이상 공유) + 유입 상한 2개. SearchGPT vs Sora near-miss 추가.
- 분수 "100만분의 1" 잔존 오탐 + "30분의 10분" 부분 마스킹.
- 재수리 프롬프트 모순 문구 명확화 + 보너스 attempt 시간 예산 강화
  (4차 120초, 저노력 재시도 없음).
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import (
    REPAIR_JSON_PROMPT,
    _ATTEMPT_TIMEOUTS,
    _parse_or_repair_json,
    _should_retry_timeout,
    attach_sources,
    render_feedback,
)
from run import draft_with_retry
from validate import (
    _analysis_number_canons,
    _numbers_grounded_detail,
    keynums_link_findings,
    url_core,
)

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}", file=sys.stderr)


def _collected(*items):
    return {url_core(it["url"]): it for it in items}


def _analysis(body, sources, bullets=None, title="AI 시장 28% 성장"):
    return {
        "id": "a1",
        "title": title,
        "bullets": bullets if bullets is not None else ["시장이 28% 성장했다"],
        "body": [body] if isinstance(body, str) else body,
        "takeaway": "성장세가 이어진다.",
        "sources": [{"url": u} for u in sources],
    }


# ============================================================
# 1. 분수 오탐 "4분" (P18 "3분기"→"3분"과 같은 계열)
# ============================================================
_URL28 = "https://example.com/news/ai-growth"
_C28 = _collected({
    "title": "AI market grows 28%",
    "summary": "The AI market grew 28% this year, beating forecasts.",
    "url": _URL28,
})
_A_FRAC = _analysis("전체 시장의 4분의 1을 넘는 28% 성장세를 보였다.", [_URL28])

ok("분수: canon에서 4분 제외",
   _analysis_number_canons(_A_FRAC) == {"28%"})
_d = _numbers_grounded_detail(_A_FRAC, _C28)
ok("분수: 4분의 1 + 28%만 있을 때 통과",
   _d["grounded"] and _d["bad"] == [])
ok("분수: allowed_raw에 28%만 있음", _d["allowed_raw"] == ["28%"])

# 실제 시간 단위 "4분"은 여전히 차단 (과잉 마스킹 방지)
_A_MIN = _analysis("4분 만에 28% 상승했다.", [_URL28])
_dmin = _numbers_grounded_detail(_A_MIN, _C28)
ok("분수: 실제 4분(시간)은 여전히 차단",
   not _dmin["grounded"] and any(b["raw"] == "4분" for b in _dmin["bad"]))

# "3분의 2" 변형 + EN↔KO 표면 쌍 (입력 "a quarter", 출력 "4분의 1")
_A_FRAC2 = _analysis("시장의 3분의 2를 차지하는 28% 성장세다.", [_URL28])
ok("분수: 3분의 2도 통과",
   _numbers_grounded_detail(_A_FRAC2, _C28)["grounded"])
_C_Q = _collected({
    "title": "A quarter of users switched",
    "summary": "A quarter of users switched to the new model.",
    "url": _URL28,
})
_A_Q = _analysis("사용자의 4분의 1이 새 모델로 갈아탔다.", [_URL28],
                 bullets=["사용자의 4분의 1이 갈아탔다"])
# P26b: 이 테스트는 EN↔KO 의미 정합성을 검증하지 않는다 — 양쪽 모두
# 추출 수치가 0개라 통과하는 vacuous truth이다. 분수는 수치 검증에서
# 면제되므로(마스킹), "차단되지 않음"만 확인한다. 분수→소수·퍼센트
# 정규화(1/4 ↔ 25%)는 백로그.
ok("분수: a quarter 입력 + 4분의 1 출력이 차단되지 않음 (분수는 검증 면제)",
   _numbers_grounded_detail(_A_Q, _C_Q)["grounded"])

# P26b: 단위 포함 분수 "100만분의 1" — "100만"이 추출돼 차단되던 잔존 오탐
_A_FRAC3 = _analysis("100만분의 1 확률로 28% 성장했다.", [_URL28])
ok("분수: 100만분의 1 마스킹 (100만 미추출)",
   _analysis_number_canons(_A_FRAC3) == {"28%"})
ok("분수: 100만분의 1 + 28% 통과",
   _numbers_grounded_detail(_A_FRAC3, _C28)["grounded"])

# P26b: 분모에 단위가 붙은 경우 "30분의 10분" — "N분의"만 지우고
# "10분"은 정상 수치로 남겨 검증한다 ("30분"은 마스킹됨)
_A_FRAC4 = _analysis("회의 30분의 10분을 할애해 28% 성장 방안을 논의했다.", [_URL28])
_c4 = _analysis_number_canons(_A_FRAC4)
ok("분수: 30분의 10분에서 10분은 추출됨",
   "10분" in _c4 and "28%" in _c4)
ok("분수: 30분의 10분에서 30분은 마스킹됨",
   "30분" not in _c4)

# P26b: 공백 변형 "4분 의 1"도 마스킹
_A_FRAC5 = _analysis("사용자의 4분 의 1이 28% 성장했다.", [_URL28])
ok("분수: 4분 의 1(공백 변형) 마스킹",
   _analysis_number_canons(_A_FRAC5) == {"28%"})

# keynums 스캔: "28%"는 연결되고 "4분"은 연결되지 않음
_issue_frac = {"analysis": [_A_FRAC], "keynums": [
    {"val": "28%", "lab": "시장 성장률", "sub": "example.com"},
    {"val": "4분", "lab": "소요 시간", "sub": "example.com"},
]}
_fl = keynums_link_findings(_issue_frac)
ok("분수: keynums 28% 연결됨",
   all(f["val"] != "28%" for f in _fl))
ok("분수: keynums 4분 미연결로 지적됨",
   any(f["val"] == "4분" for f in _fl))

# ============================================================
# 2a. 허용 집합 — 같은 스토리 그룹까지 확장
# ============================================================
_URL_A = "https://techcrunch.com/anthropic-ipo-plans"
_URL_B = "https://www.reuters.com/anthropic-valuation-81-billion"
_ITEMS_AB = [
    {"title": "Anthropic plans IPO after revenue surge",
     "summary": "Anthropic is preparing an IPO.",
     "url": _URL_A, "source": "TechCrunch"},
    {"title": "Anthropic IPO plans advance as valuation hits $81.3 Billion",
     "summary": "Anthropic is valued at $81.3 Billion as IPO talks advance.",
     "url": _URL_B, "source": "Reuters"},
]
_A_IPO = _analysis("기업가치는 813억 달러로 평가받는다.", [_URL_A],
                   bullets=["기업가치 813억 달러 수준"], title="앤트로픽 IPO 추진")
_dipo = _numbers_grounded_detail(_A_IPO, _collected(*_ITEMS_AB))
ok("그룹 확장: $81.3B → 813억 통과",
   _dipo["grounded"] and _dipo["bad"] == [])
ok("그룹 확장: allowed_raw에 $81.3 Billion 포함",
   any("$81.3 Billion" in r for r in _dipo["allowed_raw"]))

_A_400 = _analysis("기업가치는 4000억 달러로 평가받는다.", [_URL_A],
                   bullets=["기업가치 4000억 달러 수준"], title="앤트로픽 IPO 추진")
_ITEMS_AB400 = [
    dict(_ITEMS_AB[0]),
    {"title": "Anthropic IPO plans advance as valuation hits $400 Billion",
     "summary": "Anthropic is valued at $400 Billion as IPO talks advance.",
     "url": _URL_B, "source": "Reuters"},
]
ok("그룹 확장: $400B → 4000억 통과",
   _numbers_grounded_detail(_A_400, _collected(*_ITEMS_AB400))["grounded"])

# 무관 이야기의 수치는 흡수하지 않음 (과잉 확장 방지)
_URL_C = "https://www.reuters.com/openai-99-billion"
_ITEMS_ABC = _ITEMS_AB + [
    {"title": "OpenAI raises $99 Billion in new round",
     "summary": "OpenAI raised $99 Billion.",
     "url": _URL_C, "source": "Reuters"},
]
_A_990 = _analysis("기업가치는 990억 달러로 평가받는다.", [_URL_A],
                   bullets=["기업가치 990억 달러 수준"], title="앤트로픽 IPO 추진")
_d990 = _numbers_grounded_detail(_A_990, _collected(*_ITEMS_ABC))
ok("그룹 확장: 무관 이야기 $99B → 990억은 여전히 차단",
   not _d990["grounded"] and any(b["raw"] == "990억" for b in _d990["bad"]))

# P26b near-miss: 같은 회사 다른 사건 — SearchGPT vs Sora.
# Jaccard 0.40으로 story_groups가 묶지만 공유 제목 토큰이 2개
# ({openai, launches})라 확장 기준(3개 이상)에 미달한다.
_URL_SG = "https://techcrunch.com/openai-searchgpt"
_URL_SORA = "https://www.theverge.com/openai-sora-app"
_ITEMS_SG = [
    {"title": "OpenAI launches SearchGPT",
     "summary": "OpenAI launched SearchGPT, an AI search engine.",
     "url": _URL_SG, "source": "TechCrunch"},
    {"title": "OpenAI launches Sora app",
     "summary": "OpenAI launched the Sora app at $20 per month.",
     "url": _URL_SORA, "source": "The Verge"},
]
_A_SG = _analysis("서치GPT 이용료는 월 20달러이다.", [_URL_SG],
                  bullets=["서치GPT가 출시됐다"], title="서치GPT 출시")
_dsg = _numbers_grounded_detail(_A_SG, _collected(*_ITEMS_SG))
ok("그룹 확장: SearchGPT vs Sora — Sora $20 누출 차단",
   not _dsg["grounded"] and any(b["raw"] == "20달러" for b in _dsg["bad"]))

# P26b near-miss: Google DeepMind robotics vs quantum — 공유 토큰
# {google, deepmind} 2개로 확장 기준 미달.
_URL_RB = "https://example.com/deepmind-robotics"
_URL_QT = "https://example.com/deepmind-quantum"
_ITEMS_RQ = [
    {"title": "Google deepmind robotics",
     "summary": "Google DeepMind unveiled a new robotics system.",
     "url": _URL_RB, "source": "TechCrunch"},
    {"title": "Google deepmind quantum",
     "summary": "Google DeepMind's quantum chip shipped 1,000 units.",
     "url": _URL_QT, "source": "The Verge"},
]
_A_RQ = _analysis("로봇 칩은 1000개 수준이다.", [_URL_RB],
                  bullets=["로봇 시스템이 공개됐다"], title="딥마인드 로봇")
_dr = _numbers_grounded_detail(_A_RQ, _collected(*_ITEMS_RQ))
ok("그룹 확장: robotics vs quantum — 양자 1000 누출 차단",
   not _dr["grounded"] and any(b["raw"] == "1000개" for b in _dr["bad"]))

# P26b: 유입 상한 — 기준을 통과하는 그룹 아이템이 3개여도 확장
# 허용은 최대 2개. 3번째 아이템(B3, $83B)의 수치는 허용 집합에
# 들어가지 않는다. (B2·B3 모두 자체 출처와 제목 토큰 3개 공유)
_URL_B2 = "https://www.bloomberg.com/anthropic-valuation-82-billion"
_URL_B3 = "https://www.ft.com/anthropic-valuation-83-billion"
_ITEMS_AB3 = _ITEMS_AB + [
    {"title": "Anthropic IPO plans continue as valuation reaches $82 Billion",
     "summary": "Anthropic valuation reached $82 Billion.",
     "url": _URL_B2, "source": "Bloomberg"},
    {"title": "Anthropic IPO plans expand as valuation tops $83 Billion",
     "summary": "Anthropic valuation topped $83 Billion.",
     "url": _URL_B3, "source": "FT"},
]
_A_CAP = _analysis("기업가치는 830억 달러로 평가받는다.", [_URL_A],
                   bullets=["기업가치 830억 달러 수준"], title="앤트로픽 IPO 추진")
_dcap = _numbers_grounded_detail(_A_CAP, _collected(*_ITEMS_AB3))
ok("그룹 확장: 유입 상한 2개 — 3번째 그룹 아이템 수치($83B → 830억) 차단",
   not _dcap["grounded"] and any(b["raw"] == "830억" for b in _dcap["bad"]))
# 2번째 아이템까지는 허용됨 (상한이 1개가 아님)
_A_CAP2 = _analysis("기업가치는 820억 달러로 평가받는다.", [_URL_A],
                    bullets=["기업가치 820억 달러 수준"], title="앤트로픽 IPO 추진")
ok("그룹 확장: 유입 상한 2개 — 2번째 그룹 아이템 수치($82B → 820억) 통과",
   _numbers_grounded_detail(_A_CAP2, _collected(*_ITEMS_AB3))["grounded"])

# ============================================================
# 2b. attach_sources MUST-COVER 보강
# ============================================================
_MC_ITEMS = [
    {"title": "Critical zero-day in Acme VPN actively exploited",
     "summary": "A critical zero-day in Acme VPN is being exploited.",
     "url": "https://bleepingcomputer.com/acme-vpn-zero-day",
     "source": "BleepingComputer", "kind": "news"},
    {"title": "Acme VPN zero-day emergency patch released",
     "summary": "Acme released an emergency patch for the zero-day.",
     "url": "https://thehackernews.com/acme-vpn-patch",
     "source": "The Hacker News", "kind": "news"},
    {"title": "OpenAI releases new model",
     "summary": "OpenAI released a new model today.",
     "url": "https://openai.com/new-model",
     "source": "OpenAI", "kind": "doc"},
]
_MC_SNAP = {"items": _MC_ITEMS}
_MC_ISSUE = {"analysis": [{
    "id": "acme-vpn",
    "title": "Acme VPN 제로데이 악용",
    "bullets": ["Acme VPN zero-day가 악용되고 있다"],
    "body": ["Acme VPN의 zero-day 취약점이 악용되고 있다. 긴급 패치가 나왔다."],
    "takeaway": "패치가 필요하다.",
    "sources": [{"url": "https://openai.com/new-model"}],
}]}
_mc_out = attach_sources(_MC_ISSUE, _MC_SNAP)
_mc_srcs = [s["url"] for s in _mc_out["analysis"][0]["sources"]]
ok("MUST-COVER: 미편입 이야기 아이템이 출처에 붙음",
   "https://bleepingcomputer.com/acme-vpn-zero-day" in _mc_srcs)
ok("MUST-COVER: 기존 출처는 유지됨",
   "https://openai.com/new-model" in _mc_srcs)

# 이미 편입된 이야기는 중복 부착하지 않음
_MC_ISSUE2 = {"analysis": [{
    "id": "acme-vpn",
    "title": "Acme VPN 제로데이 악용",
    "bullets": ["Acme VPN zero-day가 악용되고 있다"],
    "body": ["Acme VPN의 zero-day 취약점이 악용되고 있다. 긴급 패치가 나왔다."],
    "takeaway": "패치가 필요하다.",
    "sources": [{"url": "https://bleepingcomputer.com/acme-vpn-zero-day"}],
}]}
_mc_out2 = attach_sources(_MC_ISSUE2, _MC_SNAP)
_mc_srcs2 = [s["url"] for s in _mc_out2["analysis"][0]["sources"]]
# P17 보충이 같은 이야기 2번째 아이템을 붙이는 것은 정상 — MUST-COVER
# 패스가 중복으로 붙이지 않았는지(각 URL 1회씩)만 확인한다.
ok("MUST-COVER: 이미 편입된 이야기는 중복 부착 없음",
   len(_mc_srcs2) == len(set(_mc_srcs2))
   and "https://bleepingcomputer.com/acme-vpn-zero-day" in _mc_srcs2)

# P26b: 회사명 1개만 겹치는 무관 분석에는 붙이지 않음.
# "Google"만 공유하는 반독점 분석에 Gemini 제로데이 출처를 붙이면
# MUST-COVER 게이트(출처 URL만 판정)가 본문 없이 통과해 버린다.
# 참고: 한글 제목 아이템은 story_groups에서 토큰이 없어 그룹 자체가
# 안 되므로 must_cover_stories 경로로는 도달하지 않는다 — fail-open
# 중화는 방어적 깊이(defense-in-depth)이며, 이 테스트는 도달 가능한
# 회사명-단일-겹침 변형으로 검증한다.
_MC_GOOGLE_ITEMS = [
    {"title": "Critical zero-day in Google Gemini 3 actively exploited",
     "summary": "A critical zero-day in Google Gemini 3 is being exploited.",
     "url": "https://bleepingcomputer.com/gemini-zero-day",
     "source": "BleepingComputer", "kind": "news"},
    {"title": "Google Gemini 3 zero-day emergency patch released",
     "summary": "Google released an emergency patch for the zero-day.",
     "url": "https://thehackernews.com/gemini-patch",
     "source": "The Hacker News", "kind": "news"},
    {"title": "OpenAI releases new model",
     "summary": "OpenAI released a new model today.",
     "url": "https://openai.com/new-model",
     "source": "OpenAI", "kind": "doc"},
]
_MC_GOOGLE_SNAP = {"items": _MC_GOOGLE_ITEMS}
_MC_ANTITRUST = {"analysis": [{
    "id": "google-antitrust",
    "title": "구글 반독점 판결",
    "bullets": ["Google 반독점 소송이 진행 중이다"],
    "body": ["Google의 시장 지배력 남용 혐의가 심리 중이다."],
    "takeaway": "판결을 지켜봐야 한다.",
    "sources": [{"url": "https://openai.com/new-model"}],
}]}
_mc_at = attach_sources(_MC_ANTITRUST, _MC_GOOGLE_SNAP)
_mc_at_srcs = [s["url"] for s in _mc_at["analysis"][0]["sources"]]
ok("MUST-COVER: 회사명만 겹치는 무관 분석에는 부착 안 함",
   "https://bleepingcomputer.com/gemini-zero-day" not in _mc_at_srcs
   and "https://thehackernews.com/gemini-patch" not in _mc_at_srcs
   and _mc_at_srcs == ["https://openai.com/new-model"])

# P26b: 진짜 분석 + 무관 분석이 함께 있으면 진짜 분석에만 붙음
_MC_BOTH = {"analysis": [
    {
        "id": "gemini-zero-day",
        "title": "Google Gemini 3 제로데이 악용",
        "bullets": ["Google Gemini 3 zero-day가 악용되고 있다"],
        "body": ["Google Gemini 3의 zero-day 취약점이 악용되고 있다. 긴급 패치가 나왔다."],
        "takeaway": "패치가 필요하다.",
        "sources": [{"url": "https://openai.com/new-model"}],
    },
    {
        "id": "google-antitrust",
        "title": "구글 반독점 판결",
        "bullets": ["Google 반독점 소송이 진행 중이다"],
        "body": ["Google의 시장 지배력 남용 혐의가 심리 중이다."],
        "takeaway": "판결을 지켜봐야 한다.",
        "sources": [{"url": "https://openai.com/new-model"}],
    },
]}
_mc_both = attach_sources(_MC_BOTH, _MC_GOOGLE_SNAP)
_mc_genuine = [s["url"] for s in _mc_both["analysis"][0]["sources"]]
_mc_unrel = [s["url"] for s in _mc_both["analysis"][1]["sources"]]
ok("MUST-COVER: 진짜 분석에만 부착, 무관 분석에는 부착 안 함",
   "https://bleepingcomputer.com/gemini-zero-day" in _mc_genuine
   and "https://bleepingcomputer.com/gemini-zero-day" not in _mc_unrel)

# P26b: 차순위 순회 — 최적 쌍이 4개 상한에 걸리면 차순위 analysis에 붙음.
# analysis1(최적, 출처 4개)은 P16 필터를 통과하도록 본문에 4개 출처
# 주제를 언급한다. analysis2의 기존 출처(OpenAI)는 Acme 그룹과 무관해
# P17 보충이 간섭하지 않는다.
_MC_FILLERS = [
    {"title": "Google Pixel phone price drops",
     "summary": "Google Pixel phone price dropped.",
     "url": "https://www.theverge.com/pixel-price",
     "source": "The Verge", "kind": "news"},
    {"title": "Microsoft Teams update rolls out",
     "summary": "Microsoft Teams update rolled out.",
     "url": "https://www.wired.com/teams-update",
     "source": "Wired", "kind": "news"},
    {"title": "AI index hits new high",
     "summary": "The AI index hit a new high.",
     "url": "https://www.bloomberg.com/ai-index",
     "source": "Bloomberg", "kind": "news"},
]
_MC_RANK_SNAP = {"items": _MC_ITEMS + _MC_FILLERS}
_MC_RANK = {"analysis": [
    {
        "id": "acme-vpn-1",
        "title": "Acme VPN 제로데이 악용",
        "bullets": ["Acme VPN zero-day가 악용되고 있다"],
        "body": ["Acme VPN의 zero-day 취약점이 악용되고 있다. 긴급 패치가 나왔다. "
                 "Google Pixel 가격 인하와 Microsoft Teams 업데이트, AI index 최고치도 같은 날 발표됐다."],
        "takeaway": "패치가 필요하다.",
        "sources": [{"url": "https://openai.com/new-model"},
                    {"url": "https://www.theverge.com/pixel-price"},
                    {"url": "https://www.wired.com/teams-update"},
                    {"url": "https://www.bloomberg.com/ai-index"}],
    },
    {
        "id": "acme-vpn-2",
        "title": "Acme VPN 제로데이 악용",
        "bullets": ["Acme VPN zero-day가 악용되고 있다"],
        "body": ["Acme VPN의 zero-day 취약점이 악용되고 있다. 긴급 패치가 나왔다."],
        "takeaway": "패치가 필요하다.",
        "sources": [{"url": "https://openai.com/new-model"}],
    },
]}
_mc_rank = attach_sources(_MC_RANK, _MC_RANK_SNAP)
_mc_r1 = [s["url"] for s in _mc_rank["analysis"][0]["sources"]]
_mc_r2 = [s["url"] for s in _mc_rank["analysis"][1]["sources"]]
ok("MUST-COVER: 차순위 순회 — 상한에 걸린 최적 분석은 건너뛰고 차순위에 부착",
   "https://bleepingcomputer.com/acme-vpn-zero-day" not in _mc_r1
   and "https://bleepingcomputer.com/acme-vpn-zero-day" in _mc_r2)

# ============================================================
# 4a. 같은 attempt 내 JSON 재수리
# ============================================================
_called = {"n": 0}


def _stub_fixed(user):
    _called["n"] += 1
    return '{"a": 1}'


def _stub_never(user):
    _called["n"] += 1
    raise AssertionError("repair must not be called for valid JSON")


def _stub_raise(user):
    raise RuntimeError("LLM down")


def _stub_garbage(user):
    return "still not json {{{"


ok("JSON 수리: 유효 JSON은 수리 호출 없이 파싱",
   _parse_or_repair_json('{"a": 1}', _stub_never) == ({"a": 1}, None)
   and _called["n"] == 0)
ok("JSON 수리: 깨진 JSON을 수리 호출로 복구",
   _parse_or_repair_json("not json at all", _stub_fixed) == ({"a": 1}, None))
ok("JSON 수리: 수리 호출 실패 시 (None, 에러)",
   _parse_or_repair_json("not json at all", _stub_raise)[0] is None
   and _parse_or_repair_json("not json at all", _stub_raise)[1] != "")
ok("JSON 수리: 수리 후에도 파싱 실패 시 (None, 에러)",
   _parse_or_repair_json("not json at all", _stub_garbage)[0] is None)

# JSON 파싱 실패 sidecar가 다음 attempt 피드백에 실림
_f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
json.dump({"file": "x", "date": "2026-11-19", "failed": True,
           "errors": [{"code": "SCHEMA-001",
                       "message": "JSON 파싱 실패: model did not return parseable JSON"}]},
          _f, ensure_ascii=False)
_f.close()
ok("JSON 수리: 파싱 실패 sidecar가 피드백에 렌더링됨",
   "JSON 파싱 실패" in render_feedback(_f.name))

# ============================================================
# 4b. LLM 타임아웃 시 보너스 attempt
# ============================================================
def _bonus_wire(rcs, validate_rc=0):
    calls: list = []
    d = Path(tempfile.mkdtemp())
    date = "2026-11-19"
    issue_file = d / "issue.json"
    it = iter(rcs)

    def fake_sh(cmd):
        calls.append(cmd)
        rc = next(it)
        if rc == 0:
            issue_file.write_text("{}", encoding="utf-8")
        return rc

    def fake_validate(json_out=None, attempt=None):
        return validate_rc

    rc = draft_with_retry(["draft"], issue_file, fake_validate, max_attempts=3,
                          sh_fn=fake_sh, sleep_fn=lambda s: None,
                          pipe_dir=d, date=date)
    return rc, [c for c in calls if "--attempt" in c]


_rc, _cmds = _bonus_wire([5, 5, 5, 0])
ok("타임아웃 보너스: 3회 타임아웃 뒤 4번째 시도 성공", _rc == 0)
ok("타임아웃 보너스: draft 4회 호출", len(_cmds) == 4)
ok("타임아웃 보너스: 4번째 호출이 --attempt 4",
   "--attempt" in _cmds[3] and "4" in _cmds[3][_cmds[3].index("--attempt") + 1])

_rc, _cmds = _bonus_wire([1, 1, 1])
ok("타임아웃 보너스: 검증 실패에는 보너스 없음 (3회)", len(_cmds) == 3)
ok("타임아웃 보너스: 검증 실패 rc 유지", _rc == 1)

_rc, _cmds = _bonus_wire([5, 0])
ok("타임아웃 보너스: 1회 타임아웃 뒤 성공 시 2회로 종료", _rc == 0 and len(_cmds) == 2)

# 피드백 역방향 탐색: attempt 2 타임아웃 시 attempt 3은 attempt 1 sidecar를 받음
def _fb_wire():
    calls: list = []
    d = Path(tempfile.mkdtemp())
    date = "2026-11-19"
    issue_file = d / "issue.json"
    seq = iter([0, 5, 0])

    def fake_sh(cmd):
        calls.append(cmd)
        rc = next(seq)
        if rc == 0:
            issue_file.write_text("{}", encoding="utf-8")
        return rc

    def fake_validate(json_out=None, attempt=None):
        if json_out is not None:
            json_out.write_text(
                json.dumps({"errors": [{"code": "NUMBERS-UNGROUNDED"}]}),
                encoding="utf-8")
        return 1

    rc = draft_with_retry(["draft"], issue_file, fake_validate, max_attempts=3,
                          sh_fn=fake_sh, sleep_fn=lambda s: None,
                          pipe_dir=d, date=date)
    return rc, [c for c in calls if "--attempt" in c], d, date


_rc, _cmds, _d, _date = _fb_wire()
ok("피드백 역탐색: attempt 3이 attempt 1 sidecar를 받음",
   len(_cmds) == 3 and "--feedback" in _cmds[2]
   and str(_d / f"{_date}.validate-errors.attempt1.json") in _cmds[2])

# ============================================================
# 4c. 보너스 attempt 시간 예산 (P26b)
# ============================================================
ok("시간 예산: 1~3차 타임아웃 유지 (300/240/180)",
   _ATTEMPT_TIMEOUTS[1] == 300 and _ATTEMPT_TIMEOUTS[2] == 240
   and _ATTEMPT_TIMEOUTS[3] == 180)
ok("시간 예산: 보너스 attempt(4차) 타임아웃 120초",
   _ATTEMPT_TIMEOUTS[4] == 120)
ok("시간 예산: 보너스 attempt는 저노력 재시도 없음",
   _should_retry_timeout(3) and not _should_retry_timeout(4))
# 최악 LLM 예산: 1~3차 (타임아웃 + 절반 재시도) + 보너스 120초.
# 450+360+270+120 = 1,200초로 30분(1,800초) 스텝 예산 안에 든다.
# 주의: 이 assert는 LLM 타임아웃+재시도만 합산하고 수리 호출(JSON·요약,
# attempt당 최대 2회 × 120초)은 포함하지 않는다. 수리 포함 병리적
# 최악은 약 1,950초로 30분 예산을 넘을 수 있으나, 매 attempt가
# 타임아웃 직전 성공 + 수리 2종 최대 소모 + 검증 실패가 4연속 겹쳐야
# 하는 경우라 현실 경로에서는 도달하지 않는다 (재리뷰 확인).
_worst_llm = sum(_ATTEMPT_TIMEOUTS[a] + max(60, _ATTEMPT_TIMEOUTS[a] // 2)
                 for a in (1, 2, 3)) + _ATTEMPT_TIMEOUTS[4]
ok("시간 예산: 최악 LLM 합산(수리 제외) 1,500초 이내",
   _worst_llm <= 1500)
ok("재수리 프롬프트: 잘린 뒷부분 닫기 명시 (추가/삭제 금지와 충돌 해소)",
   "잘린 뒷부분은 문법에 맞게 닫되" in REPAIR_JSON_PROMPT)

print(f"P26 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
