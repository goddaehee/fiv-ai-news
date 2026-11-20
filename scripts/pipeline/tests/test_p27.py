#!/usr/bin/env python3
"""P27 회귀 테스트: 2026-11-20호 — 페이로드 확장 + 헤드라인 가드 + 세기 숫자 +
본문 결정적 확장 + 2차 보충 엄격화.

실측 실패 원인 (run 44656448099, 로그·아티팩트·로컬 재현 3중 확인):
1. 허용 집합 범위 — P26 확장이 3 attempt 통틀어 0건 발동했다.
   차단된 세 아이템(WSJ $1.5T·Verge $111·TC $83)은 전부 스토리 그룹
   싱글턴이라 그룹 소속 조건에서 이미 막히고, 자체 출처와 제목 토큰
   겹침도 1~2개라 토큰 기준 완화(3→2)만으로는 아무것도 고쳐지지
   않는다. LLM이 쓴 수치는 사실 페이로드 아이템("starts trading"
   요약의 $111.50·$83·$1.5T)에서 온 것이다 — LLM이 본 입력에 있는데
   출처에서 빠져 차단됐다.
   → 허용 집합을 버킷 페이로드( LLM 가시 입력, 최대 6개 대표)까지
   넓히되, (a) 페이로드 대표이고 (b) analysis ID 토큰과 제목 토큰을
   1개 이상 공유하고 (c) 공유 토큰이 인용 출처 제목에도 있고
   (d) 인용 출처와 같은 스토리 그룹이 아닌 아이템만 허용한다.
   같은 그룹 아이템은 P26의 엄격 기준(제목 토큰 3개 이상 공유)이
   판단한다 — P27은 그룹이 쪼개진 경우만 다룬다.
2. 헤드라인 누락 — attempt 3의 LLM 출력은 6개 분석 전부 헤드라인이
   없었다. normalize이 ID를 제목으로 쓰자("2. nvidia-china-chips")
   그 영문 토큰이 _source_overlap 판정을 오염시켜 잘못 복사된
   Alibaba CBM URL이 살아남았고, 2차 보충이 돌지 않아 모틀리풀
   아이템이 붙지 않았다.
   → ID 폴백 제목은 겹침 계산에서 제외하고, 헤드라인 전량 누락 시
   SchemaError로 빨리 실패시켜 다음 attempt 피드백에 포함시킨다.
3. 세기 숫자 — "8개 보안업체"가 11/19에 이어 재발했다. THN 요약에
   8곳이 나열돼 있어 LLM이 이름을 세어 썼는데, 게이트는 세기 추론을
   검증할 수 없다.
   → 프롬프트에 "이름을 세어 만든 개수는 쓰지 않는다"를 명시한다.
4. 본문 밀도 — PR #122만으로는 수렴하지 않는다 (attempt 2에서 4개
   분석이 544~571자로 미달했다가 attempt 3에서 회복 — 문턱 근처
   요동). P26에서 빼둔 불릿 병합이 여전히 필요하다.
   → 최종 attempt에서만 완결 문장인 불릿을 새 문단으로 병합해
   600자까지 채운다 (명사형 불릿은 P17 비문 교훈으로 제외).
5. 2차 보충 — openai-performance-factory(doc)에 IPO 소송 기사가
   붙어 DEPTH 함정이 생겼다. "openai"가 제목 토큰으로는 희귀해
   (df=2) overlap 1 + 희귀 토큰 공유 두 조건을 회사명 하나로 통과했다.
   → doc-kind 분석에는 2차 보충을 하지 않는다 (공식 문서 단독 출처는
   완결된 이야기이고, P22 SOURCES-THIN도 doc 단독을 제외한다).
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import (
    PROMPT,
    SchemaError,
    _source_overlap,
    _title_is_id_fallback,
    attach_sources,
    normalize,
    render_feedback,
    thicken_body,
)
from validate import (
    _numbers_grounded_detail,
    url_core,
)
from cluster import _story_tokens

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


def _it(title, summary, url, source="X", kind="news"):
    return {"title": title, "summary": summary, "url": url,
            "source": source, "kind": kind}


def _analysis(body, sources, bullets=None, title="AI 시장 28% 성장",
              aid="a1"):
    return {
        "id": aid,
        "title": title,
        "bullets": bullets if bullets is not None else ["시장이 28% 성장했다"],
        "body": [body] if isinstance(body, str) else body,
        "takeaway": "성장세가 이어진다.",
        "sources": [{"url": u} for u in sources],
    }


# ============================================================
# 1. 페이로드 확장 — starts-trading 패턴 (11/20 실측 재현)
# ============================================================
# own: WSJ "What to Know About Anthropic's Record-Breaking IPO" (그룹
# 대표, coverage 6 그룹의 일원). payload: starts-trading 아이템은
# coverage 3 그룹의 대표라 페이로드에 들어간다. ID "anthropic-ipo"와
# 제목 토큰 "anthropic"을 공유한다. 그 요약에 $111.50·$83·$1.5T가
# 전부 들어 있다.
_URL_OWN = "https://news.google.com/rss/articles/CBMown"
_URL_WSJK = "https://news.google.com/rss/articles/CBMwsjknow"
_URL_ST = "https://example.com/anthropic-starts-trading"
_URL_BB = "https://example.com/anthropic-blockbuster"
_ITEMS_A = [
    _it("What to Know About Anthropic's Record-Breaking IPO",
        "Anthropic's IPO is a record-breaking debut.",
        _URL_WSJK, "Anthropic GNews"),
    _it("Who is getting rich from Anthropic's record IPO",
        "Investors are getting rich from Anthropic's IPO.",
        "https://news.google.com/rss/articles/CBMrich", "Anthropic GNews"),
    _it("Anthropic Shares Jump 17% After $107.3 Billion IPO Breaks Record",
        "Anthropic shares jumped 17% after a $107.3 Billion IPO.",
        "https://news.google.com/rss/articles/CBMjump", "Anthropic GNews"),
    _it("Anthropic's blockbuster debut tests Wall Street's faith in AI boom",
        "Anthropic's blockbuster debut tests Wall Street's faith.",
        _URL_BB, "Reuters"),
    _it("Anthropic starts trading on Wall Street",
        'Anthropic has officially gone public. It began trading on the '
        'Nasdaq under the ticker symbol "ANT" at $111.50 per share, up '
        "from its initial $83 per share price that put company's value "
        "at around $1.5 trillion.",
        _URL_ST, "Reuters"),
    _it("San Francisco-based Anthropic ends Wall Street debut valued at $1.27T",
        "Anthropic ends its debut valued at $1.27T.",
        "https://example.com/anthropic-ends-debut", "USA Today"),
]
_A_PAY = _analysis(
    "앤스로픽이 나스닥에서 거래를 시작했습니다. 첫 거래 가격은 주당 "
    "111.50달러로 공모가인 83달러보다 크게 높은 수준에서 출발했습니다. "
    "공모가를 기준으로 회사 가치는 약 1.5조 달러로 매겨졌습니다.",
    [_URL_WSJK],
    bullets=["첫 거래 가격은 111.50달러였다"],
    title="공모가 83달러에서 시초가 111.50달러로 시작한 첫 거래일",
    aid="anthropic-ipo")
_dpay = _numbers_grounded_detail(_A_PAY, _collected(*_ITEMS_A))
ok("페이로드 확장: starts-trading 경유 1.5조·111.50달러·83달러 통과",
   _dpay["grounded"] and _dpay["bad"] == [])
ok("페이로드 확장: allowed_raw에 $1.5 trillion·$111.50·$83 포함",
   any("1.5 trillion" in r for r in _dpay["allowed_raw"])
   and any("111.50" in r for r in _dpay["allowed_raw"])
   and any("$83" in r for r in _dpay["allowed_raw"]))

# 싱글턴 WSJ $1.5T 아이템은 페이로드 대표라 근거가 된다 — ID 토큰
# "anthropic"을 공유하고 인용 출처 제목에도 "anthropic"이 있어
# 확증된다. $1.5T는 LLM이 본 입력에 있는 참된 수치라 허용이 옳다
# (11/20의 1.5조는 starts-trading 경유로도 풀린다). 경계 명시:
# 페이로드에 없는 아이템의 수치는 허용하지 않는다 — 다른 버킷
# Motley $1000 케이스(아래)가 그 경계다.
_URL_WSJ15 = "https://example.com/wsj-1-5-trillion"
_ITEMS_WSJSOLO = [
    _it("What to Know About Anthropic's Record-Breaking IPO",
        "Anthropic's IPO is a record-breaking debut.",
        _URL_WSJK, "Anthropic GNews"),
    _it("Is Anthropic Worth $2 Trillion, or $1.5 Trillion? How to Make Sense of the Valuations",
        "Is Anthropic worth $2 Trillion, or $1.5 Trillion?",
        _URL_WSJ15, "WSJ"),
]
_A_WSJSOLO = _analysis(
    "공모가를 기준으로 회사 가치는 약 1.5조 달러로 매겨졌습니다.",
    [_URL_WSJK],
    bullets=["회사 가치 1.5조 달러 수준"],
    title="앤스로픽 기업가치 1.5조 달러",
    aid="anthropic-ipo")
_dwsj = _numbers_grounded_detail(_A_WSJSOLO, _collected(*_ITEMS_WSJSOLO))
ok("페이로드 확장: 페이로드 대표 WSJ $1.5T는 근거 처리됨 (참된 수치)",
   _dwsj["grounded"] and _dwsj["bad"] == [])

# 오염 방지: SearchGPT vs Sora — Sora는 페이로드에 있어도 id 토큰
# 공유가 0개라 차단된다.
_URL_SG = "https://techcrunch.com/openai-searchgpt"
_URL_SORA = "https://www.theverge.com/openai-sora-app"
_ITEMS_SG = [
    _it("OpenAI launches SearchGPT",
        "OpenAI launched SearchGPT, an AI search engine.",
        _URL_SG, "TechCrunch"),
    _it("OpenAI launches Sora app",
        "OpenAI launched the Sora app at $20 per month.",
        _URL_SORA, "The Verge"),
]
_A_SG = _analysis("서치GPT 이용료는 월 20달러이다.", [_URL_SG],
                  bullets=["서치GPT가 출시됐다"], title="서치GPT 출시",
                  aid="searchgpt")
_dsg = _numbers_grounded_detail(_A_SG, _collected(*_ITEMS_SG))
ok("페이로드 확장: SearchGPT vs Sora — Sora $20 누출 차단",
   not _dsg["grounded"] and any(b["raw"] == "20달러" for b in _dsg["bad"]))

# 오염 방지: deepmind robotics vs quantum — quantum은 id 토큰
# "deepmind"를 공유하지만 인용 출처와 같은 스토리 그룹이라 P27은
# 건드리지 않고, P26 기준(제목 토큰 공유 2개 < 3개)이 차단한다.
_URL_RB = "https://example.com/deepmind-robotics"
_URL_QT = "https://example.com/deepmind-quantum"
_ITEMS_RQ = [
    _it("Google deepmind robotics",
        "Google DeepMind unveiled a new robotics system.",
        _URL_RB, "TechCrunch"),
    _it("Google deepmind quantum",
        "Google DeepMind's quantum chip shipped 1,000 units.",
        _URL_QT, "The Verge"),
]
_A_RQ = _analysis("로봇 칩은 1000개 수준이다.", [_URL_RB],
                  bullets=["로봇 시스템이 공개됐다"], title="딥마인드 로봇",
                  aid="deepmind-robotics")
_dr = _numbers_grounded_detail(_A_RQ, _collected(*_ITEMS_RQ))
ok("페이로드 확장: robotics vs quantum — 같은 그룹이라 P26 기준이 차단",
   not _dr["grounded"] and any(b["raw"] == "1000개" for b in _dr["bad"]))

# 오염 방지: 다른 버킷 아이템은 페이로드가 달라도 차단된다
# (Motley Fool IPO 아이템이 NVIDIA 분석에 붙지 않음 — 11/20 attempt 3).
_URL_NV = "https://www.cnbc.com/nvidia-china-chips"
_URL_MF = "https://example.com/motley-1000"
_ITEMS_MF = [
    _it("Commerce approved sales of more than 879,000 AI chips to Chinese companies",
        "Commerce approved sales of more than 879,000 AI chips.",
        _URL_NV, "CNBC"),
    _it("Here's What $1,000 Invested at Anthropic's IPO Price Is Worth Now",
        "Here's what $1,000 invested at Anthropic's IPO price is worth.",
        _URL_MF, "The Motley Fool"),
]
_A_MF = _analysis("거래 규모가 1000달러 수준이다.", [_URL_NV],
                  bullets=["거래 규모 1000달러 수준"], title="엔비디아 칩 판매",
                  aid="nvidia-china-chips")
_dmf = _numbers_grounded_detail(_A_MF, _collected(*_ITEMS_MF))
ok("페이로드 확장: 다른 버킷 Motley $1000은 NVIDIA 분석에서 차단",
   not _dmf["grounded"] and any(b["raw"] == "1000달러" for b in _dmf["bad"]))

# ============================================================
# 2a. ID 폴백 제목의 겹침 오염 제외
# ============================================================
_A_IDFB = {
    "id": "nvidia-china-chips",
    "title": "2. nvidia-china-chips",
    "bullets": ["상무부가 중국 기업행 AI 칩 판매를 승인했다"],
    "body": ["상무부가 중국 기업들에 대한 AI 칩 판매를 승인했습니다."],
    "takeaway": "승인 물량을 확인하면 됩니다.",
}
_ALIBABA = _it("Alibaba defrauded shareholders by concealing ties to "
               "suspected spy in Nvidia scandal, lawsuit says",
               "Alibaba defrauded shareholders.", "https://example.com/alibaba")
ok("헤드라인 가드: ID 폴백 제목은 겹침 계산에서 제외됨",
   _title_is_id_fallback(_A_IDFB)
   and _source_overlap(_A_IDFB, _ALIBABA) == 0)
_A_REAL = dict(_A_IDFB)
_A_REAL["title"] = "엔비디아 중국 칩 판매 승인, Nvidia 스캔들 소송"
ok("헤드라인 가드: 실제 제목의 Nvidia 토큰은 겹침으로 인정됨",
   not _title_is_id_fallback(_A_REAL)
   and _source_overlap(_A_REAL, _ALIBABA) >= 1)

# ============================================================
# 2b. 헤드라인 전량 누락 시 SchemaError
# ============================================================
_ISSUE_NOH = {
    "briefing": [
        {"id": "a", "headline": "첫 번째 이야기", "summary": "첫 번째 요약입니다."},
        {"id": "b", "headline": "두 번째 이야기", "summary": "두 번째 요약입니다."},
    ],
    "analysis": [
        {"id": "a", "bullets": ["첫 번째 불릿입니다."],
         "body": ["첫 번째 본문입니다. 배경과 맥락을 설명합니다."],
         "takeaway": "첫 번째 시사점입니다. 확인하면 됩니다."},
        {"id": "b", "bullets": ["두 번째 불릿입니다."],
         "body": ["두 번째 본문입니다. 배경과 맥락을 설명합니다."],
         "takeaway": "두 번째 시사점입니다. 확인하면 됩니다."},
    ],
}
try:
    normalize(_ISSUE_NOH, None)
    ok("헤드라인 가드: 전량 누락 시 SchemaError", False)
except SchemaError as e:
    ok("헤드라인 가드: 전량 누락 시 SchemaError", "headline" in str(e))
    ok("헤드라인 가드: 에러 메시지에 summary 없음 (요약 수리 경로 오작동 방지)",
       "summary" not in str(e))

_ISSUE_PARTIAL = {
    "briefing": [
        {"id": "a", "headline": "첫 번째 이야기", "summary": "첫 번째 요약입니다."},
        {"id": "b", "headline": "두 번째 이야기", "summary": "두 번째 요약입니다."},
    ],
    "analysis": [
        {"id": "a", "title": "첫 번째 분석 제목",
         "bullets": ["첫 번째 불릿입니다."],
         "body": ["첫 번째 본문입니다. 배경과 맥락을 설명합니다."],
         "takeaway": "첫 번째 시사점입니다. 확인하면 됩니다."},
        {"id": "b", "bullets": ["두 번째 불릿입니다."],
         "body": ["두 번째 본문입니다. 배경과 맥락을 설명합니다."],
         "takeaway": "두 번째 시사점입니다. 확인하면 됩니다."},
    ],
}
try:
    _n_partial = normalize(_ISSUE_PARTIAL, None)
    ok("헤드라인 가드: 일부 누락은 SchemaError 없이 진행 (ID 폴백)",
       _n_partial["analysis"][1]["title"] == "2. b")
except SchemaError:
    ok("헤드라인 가드: 일부 누락은 SchemaError 없이 진행 (ID 폴백)", False)

# 헤드라인 누락 sidecar가 피드백에 렌더링됨
_f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
json.dump({"file": "x", "date": "2026-11-20", "failed": True,
           "errors": [{"code": "SCHEMA-001",
                       "message": "analysis headline 전량 누락 — 제목 없이 발행할 수 없습니다"}]},
          _f, ensure_ascii=False)
_f.close()
ok("헤드라인 가드: 누락 sidecar가 피드백에 렌더링됨",
   "headline" in render_feedback(_f.name))

# ============================================================
# 3. 세기 숫자 프롬프트 규칙
# ============================================================
ok("세기 숫자: 프롬프트에 세어 만든 개수 금지 규칙 포함",
   "이름을 세어 만든 개수는 쓰지 않습니다" in PROMPT)
ok("세기 숫자: 아라비아 숫자로 적힌 값만 쓰라는 지시 포함",
   "입력에 아라비아 숫자로 적힌 값만 씁니다" in PROMPT)

# ============================================================
# 4. 본문 결정적 확장 — 최종 attempt에서만 불릿 병합
# ============================================================
_BODY_SHORT = [
    "앤스로픽이 나스닥에서 거래를 시작했습니다. 티커는 ANT이고 공모가는 주당 83달러였습니다. "
    "여러 통신사와 경제지가 데뷔를 실시간으로 중계했고, 첫 거래일 주가는 마감까지 17% 상승했습니다. "
    "상장은 회사가 계획을 공개한 지 약 한 달 만에 이뤄졌습니다. 투자은행과 기관투자자의 청약 관심이 이번 규모를 뒷받침했다는 보도가 이어졌습니다. 이번 수치는 공시를 봐야 합니다.",
    "이번 수치는 증권거래위원회 공시와 언론 보도를 함께 봐야 합니다. 공모가와 시초가, 종가의 기준이 서로 달라 단순 비교는 어렵습니다. "
    "투자은행 청약과 기관투자자 관심이 규모를 뒷받침했다는 해석도 함께 나왔습니다. 다만 상장 첫날의 들뜬 분위기가 계속될지는 아직 알 수 없습니다. "
    "실적과 현금흐름이 뒷받침되지 않으면 밸류에이션 논란이 다시 불거질 수 있습니다.",
    "배경은 AI 붐에 대한 시장의 신뢰 시험이라는 해석입니다. 상장이 성공하면 후속 기업들의 상장도 이어질 수 있습니다. "
    "다만 밸류에이션이 실적을 앞서가면 조정 가능성도 함께 거론됩니다. 조달 담당자는 상장 일정과 물량을 분리해 확인해야 합니다.",
]
_BULLETS_COMPLETE = [
    "공모가는 주당 83달러로 책정됐습니다.",
    "첫 거래일 주가는 마감까지 17% 올랐습니다.",
    "상장 계획 공개는 약 한 달 앞선 발표를 따른 것입니다.",
]
_BULLETS_FRAG = [
    "공모가 주당 83달러",
    "첫 거래일 주가 17% 상승",
]
_short_total = sum(len(p) for p in _BODY_SHORT)
ok("본문 확장: 픽스처 본문이 600자 미만임", 500 < _short_total < 600)
_merged = thicken_body(list(_BODY_SHORT), list(_BULLETS_COMPLETE), final_attempt=True)
ok("본문 확장: 최종 attempt에서 완결 불릿 병합으로 600자 도달",
   sum(len(p) for p in _merged) >= 600 and len(_merged) == 6)
ok("본문 확장: 병합된 문단은 완결 문장으로 끝남",
   all(p.rstrip().endswith(("니다.", "습니다.", "다.")) for p in _merged))
_not_merged = thicken_body(list(_BODY_SHORT), list(_BULLETS_COMPLETE), final_attempt=False)
ok("본문 확장: 최종 attempt가 아니면 병합하지 않음",
   sum(len(p) for p in _not_merged) == _short_total and len(_not_merged) == 3)
_frag = thicken_body(list(_BODY_SHORT), list(_BULLETS_FRAG), final_attempt=True)
ok("본문 확장: 명사형 불릿은 병합하지 않음 (P17 비문 방지)",
   sum(len(p) for p in _frag) == _short_total and len(_frag) == 3)
_dup = thicken_body(list(_BODY_SHORT),
                    ["이번 수치는 공시를 봐야 합니다.", _BULLETS_COMPLETE[0]],
                    final_attempt=True)
ok("본문 확장: 본문에 이미 있는 완결 문장은 중복 병합하지 않음",
   sum(len(p) for p in _dup) == _short_total + len(_BULLETS_COMPLETE[0])
   and len(_dup) == 4
   and _dup[-1] == _BULLETS_COMPLETE[0])

# normalize 경유: 최종 attempt 플래그가 실제로 thicken_body까지 닿음
_ISSUE_SHORT = {
    "briefing": [
        {"id": "anthropic-ipo", "headline": "앤스로픽 상장",
         "summary": "앤스로픽이 상장했습니다."},
    ],
    "analysis": [
        {"id": "anthropic-ipo", "title": "앤스로픽 상장 첫날",
         "bullets": list(_BULLETS_COMPLETE),
         "body": list(_BODY_SHORT),
         "takeaway": "상장 첫날의 의미를 확인하면 됩니다. 담당자는 일정을 확인하면 됩니다.",
         "sources": []},
    ],
}
_n_final = normalize(_ISSUE_SHORT, None, final_attempt=True)
ok("본문 확장: normalize 최종 attempt에서 본문 600자 도달",
   sum(len(p) for p in _n_final["analysis"][0]["body"]) >= 600)
_n_nonfinal = normalize(_ISSUE_SHORT, None, final_attempt=False)
ok("본문 확장: normalize 비최종 attempt에서는 본문 그대로",
   sum(len(p) for p in _n_nonfinal["analysis"][0]["body"]) == _short_total)

# draft.py CLI에 --attempts-total이 있고, run.py가 draft에 넘김
import subprocess
_help = subprocess.run([sys.executable, "draft.py", "--help"],
                       capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
ok("본문 확장: draft.py --attempts-total 옵션 존재",
   "--attempts-total" in _help.stdout)
_run_src = (Path(__file__).resolve().parent.parent / "run.py").read_text(encoding="utf-8")
ok("본문 확장: run.py가 draft에 --attempts-total을 넘김",
   '"--attempts-total", str(max_attempts)' in _run_src)

# ============================================================
# 5. 2차 보충 — doc-kind 분석에는 보충 안 함
# ============================================================
_PF_ITEMS = [
    _it("How OpenAI's Performance Factory keeps ChatGPT fast",
        "OpenAI's Performance Factory keeps ChatGPT fast.",
        "https://openai.com/index/how-openai-performance-factory-keeps-chatgpt-fast",
        "OpenAI News", kind="doc"),
    _it("Anthropic should give stock to Stack Overflow (and OpenAI too)",
        "Anthropic should give stock to Stack Overflow.",
        "https://news.ycombinator.com/item?id=50566487", "Hacker News", kind="talk"),
]
_PF_SNAP = {"items": _PF_ITEMS}
_PF_ISSUE = {"analysis": [{
    "id": "openai-performance-factory",
    "title": "OpenAI 퍼포먼스 팩토리",
    "bullets": ["코덱스 기반 워크플로로 성능 문제 자동 발견·수정"],
    "body": ["OpenAI가 챗GPT 응답 속도를 유지하기 위한 내부 시스템 퍼포먼스 팩토리를 공식 블로그에서 소개했습니다."],
    "takeaway": "운영 방침을 확인하면 됩니다.",
    "sources": [{"url": "https://openai.com/index/how-openai-performance-factory-keeps-chatgpt-fast"}],
}]}
_pf_out = attach_sources(_PF_ISSUE, _PF_SNAP)
_pf_srcs = [s["url"] for s in _pf_out["analysis"][0]["sources"]]
ok("2차 보충: doc-kind 분석에는 스택오버플로 아이템을 붙이지 않음",
   _pf_srcs == ["https://openai.com/index/how-openai-performance-factory-keeps-chatgpt-fast"])

# 대조: news-kind 단일 출처에는 2차 보충이 여전히 동작 (P22 동작 유지)
_Q9_ITEMS = [
    _it("NebulaCore chip ships to data centers",
        "NebulaCore chip ships to centers.",
        "https://www.bleepingcomputer.com/q9a", "BleepingComputer", kind="news"),
    _it("NebulaCore benchmarks show strong gains",
        "NebulaCore benchmarks show gains.",
        "https://techcrunch.com/q9b", "TechCrunch AI", kind="news"),
]
_Q9_SNAP = {"items": _Q9_ITEMS}
_Q9_ISSUE = {"analysis": [{
    "id": "q9", "title": "Q9 칩 출하",
    "bullets": ["Q9 칩이 출하됐다"],
    "body": ["NebulaCore 칩이 데이터센터에 출하됐습니다. 배경과 맥락을 설명합니다. 하지만 한계도 있습니다. NebulaCore 벤치마크도 공개됐습니다."],
    "takeaway": "Q9 칩 출하를 주시하면 됩니다. 담당자는 이번 주 안에 검토하면 됩니다.",
    "sources": [{"url": "https://www.bleepingcomputer.com/q9a"}],
}]}
_q9_out = attach_sources(_Q9_ISSUE, _Q9_SNAP)
_q9_srcs = [s["url"] for s in _q9_out["analysis"][0]["sources"]]
ok("2차 보충: news-kind 단일 출처에는 보충이 여전히 동작",
   len(_q9_srcs) == 2 and "https://techcrunch.com/q9b" in _q9_srcs)

print(f"P27 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
