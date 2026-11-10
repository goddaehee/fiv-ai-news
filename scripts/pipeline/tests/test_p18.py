#!/usr/bin/env python3
"""P18 회귀 테스트: 발행 안정성 — 실패 run 전수 분석에서 나온 지배 원인 4건.

배경 (실측, 2026-10-20~11-09 스케줄 21회 중 15회 실패, 전부 Draft 단계):
1. sources ≥1 미달이 거의 모든 실패 run의 최종 차단. LLM이 Google News
   토큰 URL(310자)을 복사하다 꼬리를 깨뜨려(208자만 일치) url_core 정확
   대조가 실패 → 출처 전량 탈락 (2026-11-03호 아티팩트 실증).
   → attach_sources URL 접두 복구 + 문자열 형태 수용 + 빈 출처 복구.
2. NUMBERS-UNGROUNDED 오탐 "3분": 출력 "3분기"(분기)를 "3분"으로 추출,
   입력 "Q3"/"third quarter"는 스캔 불가 → 11/03호 3 attempt 전부 재발.
   → NUM_RE에 분기 단위 + 입력 스캔에 영어 분기 표기 연결.
3. briefing summary 통째 생략 샘플 (11/06: 7개 전부 누락)이 rc=4로
   attempt를 통째로 소모. → _repair_missing_summaries 수리 호출.
4. extract_json strict 파싱 크래시 (제어문자·Extra data·트레일링 콤마).
   → 단계적 완화 파싱.
픽스처는 실측 URL·문장을 축약한 것이다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import (
    NUM_RE,
    _prefix_ref,
    _ref_table,
    _repair_missing_summaries,
    attach_sources,
    extract_json,
)
from validate import _numbers_grounded_detail, url_core

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
            "summary": summary, "published": "2026-11-03T09:00:00+09:00"}


# ---------- 1. extract_json 완화 파싱 ----------
obj = extract_json('{"a": "x\x01y", "b": 1}')
ok("extract_json: 문자열 내 제어문자 허용", obj["a"] == "x\x01y")

obj = extract_json('{"a": 1} 뒤에 붙은 잡음 {"b": 2}')
ok("extract_json: 객체 뒤 잡음은 균형 구간으로 절단", obj == {"a": 1})

obj = extract_json('{"a": [1, 2,], "b": {"c": 3,}}')
ok("extract_json: 트레일링 콤마 허용", obj["b"]["c"] == 3)

try:
    extract_json("JSON이 아닌 텍스트")
    ok("extract_json: 비JSON은 ValueError", False)
except ValueError:
    ok("extract_json: 비JSON은 ValueError", True)

# ---------- 2. URL 접두 복구 ----------
TOKEN = "xAFBVV95cUxOalN1b2NwcllWRkRjRUNmOVBjSDMxWDNzdjZIclhDNTdMMFla" * 5
GNEWS = "https://news.google.com/rss/articles/CBMi" + TOKEN  # 310자급
OTHER = "https://news.google.com/rss/articles/CBMi" + "ZZZZ" * 60
snap = {"items": [
    _it("Reuters", "Law Firm AI Use Does Not Warrant Cutting Legal Fees",
        GNEWS),
    _it("AP", "Chip Stocks Rally on Export News", OTHER),
]}
table = _ref_table(snap)
garbled = GNEWS[:210] + "Q" * 100  # 꼬리 100자 깨짐 (실측 패턴)
ok("접두 복구: 210자 일치 + 유일 → 복원",
   _prefix_ref(garbled, table) == 0)
ok("접두 복구: 짧은 URL은 복원 안 함",
   _prefix_ref("https://example.com/a", table) is None)

# 모호한 경우: 두 아이템이 긴 접두를 공유하면 복원 금지
AMB1 = "https://news.google.com/rss/articles/CBMi" + "A" * 160 + "1111"
AMB2 = "https://news.google.com/rss/articles/CBMi" + "A" * 160 + "2222"
amb_table = _ref_table({"items": [
    _it("A", "Story One", AMB1), _it("B", "Story Two", AMB2)]})
amb_llm = AMB1[:190] + "9999"  # AMB1과 190자, AMB2와 186자 일치 → margin 4
ok("접두 복구: margin 부족하면 복원 안 함",
   _prefix_ref(amb_llm, amb_table) is None)

# attach_sources 통합: 깨진 URL 1개 → canonical URL로 재조립
issue = {"analysis": [{
    "id": "law-ai-fees", "title": "법률 AI 사용, 수수료 삭감 사유 아니다",
    "bullets": ["Law Firm의 AI 사용"], "body": ["법원이 판단했다"],
    "takeaway": "", "sources": [{"url": garbled}],
}]}
attach_sources(issue, snap, ref_table=table)
srcs = issue["analysis"][0]["sources"]
ok("attach: 깨진 URL이 canonical로 복원됨",
   len(srcs) >= 1 and srcs[0]["url"] == GNEWS)

# 문자열 형태 sources 수용
issue2 = {"analysis": [{
    "id": "law-ai-fees", "title": "법률 AI", "bullets": [], "body": [],
    "takeaway": "", "sources": [GNEWS],
}]}
attach_sources(issue2, snap, ref_table=table)
ok("attach: 문자열 형태 sources 수용",
   len(issue2["analysis"][0]["sources"]) >= 1)

# ---------- 3. 빈 출처 복구 (story group) ----------
snap2 = {"items": [
    _it("Reuters", "Law Firm AI Use Does Not Warrant Cutting Legal Fees, Court Rules",
        "https://reuters.com/legal/law-firm-ai-fees"),
    _it("Bloomberg", "Law Firm Legal Fees Ruling Upheld by Appeals Court",
        "https://bloomberg.com/news/law-firm-fees"),
    _it("TechCrunch", "Quantum Chip Startup Raises Seed Round",
        "https://techcrunch.com/quantum-chip-seed"),
]}
issue3 = {"analysis": [
    {"id": "law-ai-fees", "title": "법률 AI 사용, 수수료 삭감 사유 아니다",
     "bullets": ["Law Firm의 AI 사용을 이유로 Legal Fees를 깎을 수 없다는 판결"],
     "body": ["미국 항소법원이 Law Firm의 AI 활용과 Legal Fees 산정은 별개라고 판단했다"],
     "takeaway": "", "sources": []},
    {"id": "space-weather", "title": "우주 날씨 경보",
     "bullets": ["태양풍 관측 결과"],
     "body": ["태양풍이 강해지며 위성 운용에 주의가 필요하다는 관측이 나왔다"],
     "takeaway": "", "sources": []},
]}
attach_sources(issue3, snap2, ref_table=_ref_table(snap2))
ok("빈 출처 복구: 겹침 ≥2인 story group에서 복구",
   len(issue3["analysis"][0]["sources"]) >= 1)
ok("빈 출처 복구: 겹침 없으면 빈 채로 (fail-closed)",
   len(issue3["analysis"][1]["sources"]) == 0)

# ---------- 4. 분기(quarter) 게이트 ----------
surfaces = [m.group(0) for m in NUM_RE.finditer("3분기 매출 170억 달러 공개")]
ok("NUM_RE: '3분기'는 한 덩어리로 추출", "3분기" in surfaces)
ok("NUM_RE: '3분기'에서 '3분'을 뽑지 않음", "3분" not in surfaces)
surfaces2 = [m.group(0) for m in NUM_RE.finditer("응답이 3분 만에 끝났다")]
ok("NUM_RE: 실제 '3분'은 그대로 추출", "3분" in surfaces2)

item = _it("CNBC", "Anthropic reports $17 billion in Q3 revenue",
           "https://cnbc.com/anthropic-q3",
           summary="Anthropic reports $17 billion in third quarter revenue.")
by_url = {url_core(item["url"]): item}
a_q = {"id": "anthropic-q3", "sources": [{"url": item["url"]}],
       "bullets": ["3분기 매출 170억 달러 공개"],
       "body": ["앤스로픽이 3분기 매출 170억 달러를 공개했다"],
       "takeaway": "", "extra": ""}
d = _numbers_grounded_detail(a_q, by_url)
ok("분기 grounding: '3분기'는 Q3/third quarter 근거로 통과",
   d["grounded"] and not d["bad"])
a_m = dict(a_q)
a_m["body"] = ["응답이 3분 만에 끝났다. 3분기 매출 170억 달러를 공개했다"]
a_m["bullets"] = []
d2 = _numbers_grounded_detail(a_m, by_url)
ok("분기 grounding: 근거 없는 실제 '3분'은 여전히 차단",
   not d2["grounded"] and any(b["raw"] == "3분" for b in d2["bad"]))

# ---------- 5. summary 수리 ----------
broken_issue = {
    "briefing": [
        {"id": "story-one", "headline": "첫 번째 이야기 헤드라인", "summary": ""},
        {"id": "story-two", "headline": "두 번째 이야기 헤드라인",
         "summary": "이미 있는 요약이다."},
    ],
    "analysis": [{
        "id": "story-one", "title": "첫 번째 이야기",
        "bullets": ["핵심 수치 30% 개선", "공식 발표 확인"],
        "body": ["회사 측이 새 기능을 공식 발표했다. 개선 폭은 30%로 제시됐다."],
    }],
}
snap3 = {"items": [
    _it("Official", "Story One Launch Announced",
        "https://example.org/story-one", summary="Story One launched with a 30% improvement."),
]}


def fake_chat(payload: str) -> str:
    return json.dumps({"summaries": {
        "story-one": "공식 발표에서 핵심 수치가 30% 개선됐다고 밝혔다."}})


ok("수리: 누락 summary가 채워지면 True",
   _repair_missing_summaries(broken_issue, snap3, fake_chat))
ok("수리: 채워진 summary가 실제로 들어감",
   broken_issue["briefing"][0]["summary"].startswith("공식 발표"))


def copy_chat(payload: str) -> str:
    return json.dumps({"summaries": {"story-one": "첫 번째 이야기 헤드라인"}})


broken2 = json.loads(json.dumps(broken_issue))
broken2["briefing"][0]["summary"] = ""
ok("수리: headline 복제 응답은 거부 (False)",
   not _repair_missing_summaries(broken2, snap3, copy_chat))


def dead_chat(payload: str) -> str:
    raise RuntimeError("boom")


ok("수리: 호출 실패 시 False (기존 rc=4 경로 유지)",
   not _repair_missing_summaries(broken2, snap3, dead_chat))

# ---------- 6. P18b: 영어 단위 단어형 (2026-11-10호 실측) ----------
from validate import _canon_num

ok("canon: '20x'와 '20배'는 같은 배수", _canon_num("20x") == _canon_num("20배"))
ok("canon: '20 times'와 '20배'는 같은 배수", _canon_num("20 times") == _canon_num("20배"))
ok("canon: '20배'와 '21배'는 다름", _canon_num("20배") != _canon_num("21배"))

item_cr = _it("OpenAI News", "CodeRabbit ships 20x more code",
              "https://openai.com/coderabbit",
              summary="CodeRabbit ships 20x more code, reviewing 20 times faster.")
by_cr = {url_core(item_cr["url"]): item_cr}
a_cr = {"id": "coderabbit-20x", "sources": [{"url": item_cr["url"]}],
        "bullets": ["출하량이 20배로 늘었다"], "body": [], "takeaway": "", "extra": ""}
d = _numbers_grounded_detail(a_cr, by_cr)
ok("단위 변환: '20배'는 20x/20 times 근거로 통과", d["grounded"])

item_kk = _it("OpenAI News", "Kuken searches drawings in minutes",
              "https://openai.com/kuken",
              summary="A repair drawing search now takes 4.5 minutes, down from nearly an hour.")
by_kk = {url_core(item_kk["url"]): item_kk}
a_kk = {"id": "kuken", "sources": [{"url": item_kk["url"]}],
        "bullets": ["검색이 거의 1시간에서 4.5분으로 단축"],
        "body": [], "takeaway": "", "extra": ""}
d = _numbers_grounded_detail(a_kk, by_kk)
ok("단위 변환: '4.5분'·'1시간'은 minutes/an hour 근거로 통과", d["grounded"])
a_kk2 = dict(a_kk)
a_kk2["bullets"] = ["검색이 2시간으로 단축"]
d = _numbers_grounded_detail(a_kk2, by_kk)
ok("단위 변환: 근거 없는 '2시간'은 여전히 차단", not d["grounded"])

item_em = _it("TechCrunch AI", "Meta releases Muse Ember",
              "https://techcrunch.com/ember",
              summary="At 10 cents per million input tokens, Ember is cheaper.")
by_em = {url_core(item_em["url"]): item_em}
a_em = {"id": "ember", "sources": [{"url": item_em["url"]}],
        "bullets": ["100만 토큰당 10센트"], "body": [], "takeaway": "", "extra": ""}
d = _numbers_grounded_detail(a_em, by_em)
ok("단위 변환: '100만'은 per million 근거로 통과", d["grounded"])

item_sg = _it("BleepingComputer", "SEGA breach exposes 2.2 million emails",
              "https://bleepingcomputer.com/sega",
              summary="The breach exposes 2.2 million email addresses.")
by_sg = {url_core(item_sg["url"]): item_sg}
a_sg = {"id": "sega", "sources": [{"url": item_sg["url"]}],
        "bullets": ["100만 건이 노출됐다"], "body": [], "takeaway": "", "extra": ""}
d = _numbers_grounded_detail(a_sg, by_sg)
ok("bare 보강 제한: '2.2 million'만 있으면 '100만'은 차단", not d["grounded"])
a_sg2 = dict(a_sg)
a_sg2["bullets"] = ["220만 건이 노출됐다"]
d = _numbers_grounded_detail(a_sg2, by_sg)
ok("bare 보강 제한: '220만'은 2.2 million 근거로 통과", d["grounded"])

item_pc = _it("Reuters", "Shares fall 4 percent on probe news",
              "https://reuters.com/shares",
              summary="Shares fell 4 percent after the probe was announced.")
by_pc = {url_core(item_pc["url"]): item_pc}
a_pc = {"id": "shares", "sources": [{"url": item_pc["url"]}],
        "bullets": ["주가가 4% 하락했다"], "body": [], "takeaway": "", "extra": ""}
d = _numbers_grounded_detail(a_pc, by_pc)
ok("단위 변환: '4%'는 4 percent 근거로 통과", d["grounded"])

print(f"P18 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)