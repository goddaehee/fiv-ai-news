#!/usr/bin/env python3
"""P20 회귀 테스트: 11/11호 정기 발행 실패 — P18 이후 첫 스케줄 실행에서
본슬롯·재시도 슬롯 둘 다 Draft 단계 exit 1 (run 42933900191·42948936253).

실측 실패 원인 (아티팩트 리플레이):
1. NUMBERS-UNGROUNDED 오탐 "35000개" — 입력 "35,000"(단위 없음)과 출력
   "35,000개"의 표면이 달라 차단. 6 attempt 중 5번의 최종 차단 사유.
   → 개수 단위(개·명·인·건·...) 투명화 + 한국어 복합수 전개.
2. 오탐 "2억" — 출력 "2억 5천만 달러"(=$250M 정확)를 "2억"만 보고
   차단. "5천만"은 NUM_RE에 "천"이 없어 아예 안 보였다.
   → NUM_RE에 천·조·인 추가 + 복합수 전개 ("2억 5천만" → 250000000).
3. 오탐 "7명" — 입력 "All 7 Anthropic founders"/"seven co-founders"를
   입력 스캔이 못 봤다 (작은 수·수 단어는 NUM_RE 밖).
   → 입력 스캔에 수 단어·작은 수+뒤 단어 보강.
4. 오탐 "14일, 26일" — 입력 "between October 14 and October 26"의
   월-일 날짜를 입력 스캔이 못 봤다.
   → 입력 스캔에 월-일 날짜·"N days" 보강.
5. depth numbers 슬롯 오탐 — "1.4조 달러"가 NUM_RE에 안 잡혀 analysis[0]이
   numbers+why 2개 미충족으로 attempt 2·3 연속 차단.
   → NUM_RE·_MAG_UNIT에 조(10^12)·trillion·T 추가.
6. 피드백 공백 — depth·DUP-001 에러가 sidecar에 실리지 않아 LLM이
   같은 실패를 반복했다. → collect_structured_errors + render_feedback에
   DEPTH·DUP-001 추가.
7. extract_json 크래시 — LLM이 키 여는 따옴표를 빼먹은 출력
   (`bullets": [`)에 완화 파싱 전 단계가 전부 실패해 attempt가 rc=1로
   죽었다 (재시도 슬롯 attempt 2). → bare-key 수리 단계 추가.

진짜 환각은 여전히 차단돼야 한다 ("6%"·"240,000개" — 수집 273건 전수에
없음). 픽스처는 11/11호 실측 문장을 축약한 것이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import (
    NUM_RE,
    expand_korean_compound,
    extract_json,
    normalize_num_text,
    render_feedback,
)
from validate import (
    _canon_num,
    _numbers_grounded_detail,
    collect_structured_errors,
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
        print(f"  FAIL: {name}")


def _it(source, title, url, summary=""):
    return {"source": source, "kind": "doc", "title": title, "url": url,
            "summary": summary, "published": "2026-11-11T09:00:00+09:00"}


def _grounded(analysis, items):
    by_url = {url_core(it["url"]): it for it in items}
    return _numbers_grounded_detail(analysis, by_url)


# ---------- 1. 한국어 복합수 전개 ----------
ok("복합수: '2억 5천만 달러' → '250000000 달러'",
   normalize_num_text("2억 5천만 달러") == "250000000 달러")
ok("복합수: '3만5000개' → '35000개'",
   normalize_num_text("3만5000개") == "35000개")
ok("복합수: '3만 5천 개' → '35000 개'",
   normalize_num_text("3만 5천 개") == "35000 개")
ok("복합수: '5천만' → '50000000'",
   normalize_num_text("5천만") == "50000000")
ok("복합수: '1조 2천억' → '1200000000000'",
   normalize_num_text("1조 2천억") == "1200000000000")
ok("복합수: '6억2500만' → '625000000'",
   normalize_num_text("6억2500만") == "625000000")
ok("복합수: 단일 단위 '3만'은 그대로 둔다",
   normalize_num_text("3만") == "3만")
ok("복합수: 단일 단위 '1.4조 달러'는 그대로 둔다",
   normalize_num_text("1.4조 달러") == "1.4조 달러")
ok("복합수: 법 조항 '제1조'는 건드리지 않는다",
   normalize_num_text("제1조에 따르면") == "제1조에 따르면")
ok("복합수: '3분기'·연도는 그대로 둔다",
   normalize_num_text("3분기 2026년") == "3분기 2026년")
ok("복합수 전개 헬퍼 직접 호출",
   expand_korean_compound("2억 5천만") == "250000000")

# ---------- 2. canon: 개수 단위 투명화 + 조/trillion ----------
ok("canon: '35000개' == '35000'",
   _canon_num("35000개") == _canon_num("35000") == "mag:35000")
ok("canon: '7명' == '7인' == mag:7",
   _canon_num("7명") == _canon_num("7인") == "mag:7")
ok("canon: '1.4조' == 1.4조",
   _canon_num("1.4조") == "mag:1400000000000")
ok("canon: '$1.4 trillion' == '1.4조'",
   _canon_num("$1.4 trillion") == _canon_num("1.4조"))
ok("canon: '$1.4T' == '1.4조'",
   _canon_num("$1.4T") == _canon_num("1.4조"))
ok("canon: '5천' == mag:5000",
   _canon_num("5천") == "mag:5000")
ok("canon: '%'는 투명화하지 않는다 ('6%' 유지)",
   _canon_num("6%") == "6%")
ok("canon: '14일'은 날짜로 유지",
   _canon_num("14일") == "14일")

# ---------- 3. NUM_RE: 조·천·인·trillion ----------
ok("NUM_RE: '1.4조 달러'에서 '1.4조' 추출",
   "1.4조" in [m.group(0) for m in NUM_RE.finditer("1.4조 달러")])
ok("NUM_RE: '1조원'에서 '1조' 추출",
   "1조" in [m.group(0) for m in NUM_RE.finditer("1조원")])
ok("NUM_RE: 법 조항 '제1조'는 수치로 안 본다",
   [m.group(0) for m in NUM_RE.finditer("제1조에 따르면")] == [])
ok("NUM_RE: '7인' 추출",
   "7인" in [m.group(0) for m in NUM_RE.finditer("창업자 7인")])
ok("NUM_RE: '$1.4 trillion' 추출",
   "$1.4 trillion" in [m.group(0) for m in NUM_RE.finditer("$1.4 trillion 목표")])
ok("NUM_RE: '1.4T' 추출",
   "1.4T" in [m.group(0) for m in NUM_RE.finditer("밸류에이션 1.4T")])
ok("NUM_RE: '3만5000개' → '35000개' 한 덩어리",
   [m.group(0) for m in NUM_RE.finditer(normalize_num_text("3만5000개"))] == ["35000개"])

# ---------- 4. grounding: 11/11호 오탐 4건 ----------
grok_item = _it("Ars Technica",
                "Grok Build coding agent leaks oodles of confidential info",
                "https://arstechnica.com/security/2026/11/grok-build-coding-agent-leaks-oodles-of-confidential-info-some-belonging-to-spacexsi/",
                "Researcher finds 35,000 Grok Build apps wide open to anyone who looked for them.")
a_grok = {"id": "grok-build-leak", "sources": [{"url": grok_item["url"]}],
          "bullets": ["연구자가 35,000개의 Grok Build 앱이 열려 있음을 발견했다."],
          "body": ["Grok Build 앱 35,000개가 인증 없이 열려 있었다."],
          "takeaway": "", "extra": ""}
d = _grounded(a_grok, [grok_item])
ok("grounding: '35,000개'는 입력 '35,000' 근거로 통과",
   d["grounded"] and not d["bad"])

ipo_item = _it("TechCrunch AI",
               "All 7 Anthropic founders will each cash out about $250M in IPO",
               "https://techcrunch.com/2026/11/10/all-7-anthropic-founders-ipo/",
               "Each of the seven co-founders plans to sell exactly the same number "
               "of shares in the IPO, which would bring each of them about $250 million "
               "in cash at the midpoint of the price range.")
a_ipo = {"id": "anthropic-ipo", "sources": [{"url": ipo_item["url"]}],
         "bullets": ["TechCrunch에 따르면 창업자 7명이 IPO에서 각각 2억 5천만 달러 규모를 매도할 전망이다."],
         "body": ["창업자 7인이 각각 2억 5천만 달러를 매도한다는 보도다."],
         "takeaway": "", "extra": ""}
d = _grounded(a_ipo, [ipo_item])
ok("grounding: '7명'·'2억 5천만 달러'는 입력 근거로 통과",
   d["grounded"] and not d["bad"])

qubole_item = _it("The Hacker News",
                  "Hackers Exploit Qubole's Trusted AWS Access to Breach Customer Accounts",
                  "https://thehackernews.com/2026/11/hackers-exploit-quboles-trusted-aws-access.html",
                  "An attacker broke into AWS accounts belonging to multiple Qubole "
                  "customers between October 14 and October 26 and stole stored secrets "
                  "and data, cloud security company Wiz said today.")
a_qub = {"id": "qubole-aws-breach", "sources": [{"url": qubole_item["url"]}],
         "bullets": ["침해 기간은 지난달 14일부터 26일까지로 알려졌다."],
         "body": ["공격자는 10월 14일부터 26일까지 고객 계정에 들어갔다."],
         "takeaway": "", "extra": ""}
d = _grounded(a_qub, [qubole_item])
ok("grounding: '14일, 26일'은 입력 'October 14 and October 26' 근거로 통과",
   d["grounded"] and not d["bad"])

# 기간 표기 "14 days" → "14일"
days_item = _it("BleepingComputer", "Outage lasted 14 days",
               "https://bleepingcomputer.com/outage-14-days",
               "The outage lasted 14 days before service was restored.")
a_days = {"id": "outage", "sources": [{"url": days_item["url"]}],
          "bullets": ["장애가 14일 이어졌다."], "body": [], "takeaway": "", "extra": ""}
d = _grounded(a_days, [days_item])
ok("grounding: '14일'은 입력 '14 days' 근거로 통과",
   d["grounded"] and not d["bad"])

# ---------- 5. 진짜 환각은 여전히 차단 ----------
nv_item = _it("Tom's Hardware", "Nvidia chips import probe",
              "https://tomshardware.com/nvidia-import-probe",
              "A person linked to Nvidia CEO Jensen Huang was involved in imports "
              "of Nvidia products worth $7.5B, according to reports.")
a_nv = {"id": "nvidia-huang-affair", "sources": [{"url": nv_item["url"]}],
        "bullets": [], "body": [],
        "takeaway": "",
        "extra": "그 밖에: 엔비디아 주가가 6% 넘게 하락했다는 보도도 나왔다."}
d = _grounded(a_nv, [nv_item])
ok("grounding: 근거 없는 '6%'는 여전히 차단",
   not d["grounded"] and any(b["raw"] == "6%" for b in d["bad"]))
a_nv2 = dict(a_nv)
a_nv2["extra"] = "노출된 파일이 240,000개에 달한다는 보도도 나왔다."
d = _grounded(a_nv2, [nv_item])
ok("grounding: 근거 없는 '240,000개'는 여전히 차단",
   not d["grounded"] and any("240000" in b["raw"] for b in d["bad"]))
# "조"가 있어도 크기 다르면 차단 ($80B → 800억은 통과, 80억은 차단)
a_tr = {"id": "t1", "sources": [{"url": nv_item["url"]}],
        "bullets": ["수입 규모가 80억 달러에 달한다."], "body": [],
        "takeaway": "", "extra": ""}
d = _grounded(a_tr, [nv_item])
ok("grounding: '$7.5B'와 크기 다른 '80억'은 차단",
   not d["grounded"])

# ---------- 6. depth numbers 슬롯: "1.4조 달러"가 보인다 ----------
from validate import _slot_status
a_depth = {"bullets": ["로이터가 최대 1.4조 달러 밸류에이션 목표를 단독 보도했다."],
           "body": ["Anthropic이 최대 1.4조 달러에 이르는 기업가치를 목표로 상장을 준비한다. "
                    "다만 1.4조 달러는 목표치이며 최종 상장 가격은 달라질 수 있다."],
           "takeaway": "AI 기업 밸류에이션이 달라진 지점이다. 공모가 확정 후 확인하면 된다."}
st = _slot_status(a_depth)
ok("depth: '1.4조 달러' 2회로 numbers 슬롯 충족",
   st["numbers"] is True)

# ---------- 7. extract_json: bare-key 수리 ----------
obj = extract_json('{\n  "id": "anthropic-ipo",\n  "headline": "x",\n  bullets": ["a", "b"]\n}')
ok("extract_json: 여는 따옴표 빠진 키 수리",
   obj["bullets"] == ["a", "b"] and obj["id"] == "anthropic-ipo")
obj = extract_json('{"a": 1, "b": {"c": 2,},}')
ok("extract_json: 기존 트레일링 콤마 수리는 유지",
   obj["b"]["c"] == 2)
try:
    extract_json("JSON이 아닌 텍스트")
    ok("extract_json: 비JSON은 여전히 ValueError", False)
except ValueError:
    ok("extract_json: 비JSON은 여전히 ValueError", True)

# ---------- 8. DEPTH·DUP-001 구조화 + 피드백 ----------
thin = {"id": "thin-story", "title": "얇은 기사",
        "bullets": ["짧은 불릿."],
        "body": ["짧은 본문이다."],
        "takeaway": "짧다.",
        "sources": [{"url": grok_item["url"]}]}
dup_issue = {
    "briefing": [
        # 실측 문장 (11/11호 run 1 attempt 3의 briefing[4] — DUP-001 차단됨).
        {"id": "grok-build-leak",
         "headline": "Grok Build 코딩 에이전트, 35,000개 앱 기밀 노출",
         "summary": "연구자가 Grok Build 코딩 에이전트로 만들어진 35,000개의 앱이 인증 없이 "
                    "누구에게나 열려 있다는 것을 발견했고, 스페이스X 관련 기밀도 노출된 것으로 알려졌다."},
        {"id": "other-story", "headline": "다른 이야기 헤드라인",
         "summary": "전혀 다른 내용의 요약이다. 배경과 전개가 다르다."},
    ],
    "analysis": [thin],
    "keynums": [], "tips": [],
}
errs = collect_structured_errors(dup_issue, {url_core(grok_item["url"]): grok_item})
codes = [e["code"] for e in errs]
ok("sidecar: 2개 슬롯 미충족이면 DEPTH 구조화",
   "DEPTH" in codes)
ok("sidecar: DEPTH에 미충족 슬롯 목록 포함",
   any(e["code"] == "DEPTH" and {"what", "why"} <= set(e.get("missing", []))
       for e in errs))
ok("sidecar: DUP-001 구조화",
   any(e["code"] == "DUP-001" and e.get("briefing_index") == 0 for e in errs))
# render_feedback은 sidecar 경로를 받으므로 임시 파일로 검증한다.
import json as _json
import tempfile as _tf
with _tf.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    _json.dump({"file": None, "date": "2026-11-11", "failed": True, "errors": errs},
               f, ensure_ascii=False)
    _sidecar = f.name
fb_text = render_feedback(_sidecar)
ok("feedback: DEPTH 블록 렌더링",
   "깊이 슬롯" in fb_text)
ok("feedback: DUP-001 블록 렌더링",
   "headline과 거의 같습니다" in fb_text)

print(f"P20 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
