#!/usr/bin/env python3
"""P31 회귀 테스트: 출처 회복 + 영어 단위 환산.

배경 (2026-11-24 6차 패널 평가, 게이트 7.1/10):
- 출처 평균 1.83~2.0 (목표 2.5). 원인은 세 겹이었다.
  (a) 스토리 그룹핑이 복수형 표기 차이로 쪼개짐 (customers vs Customer).
  (b) attach_sources 엄격 보충이 출처 1개에서만 동작해 2개에서 멈춤.
  (c) Google News 중계 링크가 기사 직행 링크가 아님 (origin_url은
      발행처 홈페이지뿐). 수집 단계에서 직행 URL로 해소한다.
- 영어 단위 잔존 ("40 billion", "350 million", "7.5B") — 결정적 환산으로
  한국어 단위로 바꾸되 크기는 정확히 보존한다 (validate canon 대조).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


# --- (a) 스토리 토큰 어미 정규화 -------------------------------------------
from cluster import _story_tokens, story_groups

ok("customers/customer 동일 토큰",
   "customer" in _story_tokens("steal customers API credentials")
   and "customer" in _story_tokens("targets Customer Secrets API"))
ok("companies/company 동일 토큰",
   "company" in _story_tokens("Companies unveil new models"))
ok("news는 정규화 제외", "news" in _story_tokens("Breaking news today"))
ok("glass는 ss 종결이라 유지", "glass" in _story_tokens("Google Glass returns"))

# 실제 쪼개졌던 쌍 (2026-11-25 스냅샷 실측): THN vs BleepingComputer
_pair = [
    {"source": "The Hacker News", "kind": "news",
     "title": "Microsoft Fixes Azure API Management Classic Flaw as Actor Targets Customer Secrets",
     "url": "https://thehackernews.com/azure", "summary": "", "published": None},
    {"source": "BleepingComputer", "kind": "news",
     "title": "Microsoft Azure flaw exploited to steal customers' API credentials",
     "url": "https://www.bleepingcomputer.com/azure", "summary": "", "published": None},
    {"source": "BleepingComputer", "kind": "news",
     "title": "McDonald's Japan data breach exposes customer location information",
     "url": "https://www.bleepingcomputer.com/mcd", "summary": "", "published": None},
]
_groups = story_groups(_pair)
_cov = {it["url"]: g["coverage"] for g in _groups for it in g["items"]}
ok("Azure 같은 이야기가 한 그룹 (coverage 2)",
   _cov["https://thehackernews.com/azure"] == 2
   and _cov["https://www.bleepingcomputer.com/azure"] == 2)
ok("무관한 보안 기사는 별도 그룹", _cov["https://www.bleepingcomputer.com/mcd"] == 1)

# --- (c) 중계 링크 해소 -----------------------------------------------------
from collect import decode_gnews_response, resolve_gnews_links

_resp = ('[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://techcrunch.com/2026/11/23/story/\\",1]",'
         'null,null,null,"generic"]]')
ok("디코드된 URL 추출",
   decode_gnews_response(_resp) == "https://techcrunch.com/2026/11/23/story/")
ok("깨진 응답은 None", decode_gnews_response("not json") is None)
ok("빈 응답은 None", decode_gnews_response(None) is None)


def _fake_resolver(url: str):
    if "good" in url:
        return "https://reuters.com/world/story-1"
    return None


_items = [
    {"source": "Google News AI", "kind": "news", "title": "Story one",
     "url": "https://news.google.com/rss/articles/good-token", "summary": "",
     "published": None, "origin_url": "https://www.reuters.com"},
    {"source": "Google News AI", "kind": "news", "title": "Story two",
     "url": "https://news.google.com/rss/articles/bad-token", "summary": "",
     "published": None, "origin_url": "https://www.cnn.com"},
    {"source": "Reuters", "kind": "news", "title": "Story one (direct)",
     "url": "https://reuters.com/world/story-1", "summary": "",
     "published": None},
]
_n = resolve_gnews_links(_items, resolver=_fake_resolver)
ok("해소 1건", _n == 1)
ok("해소된 아이템은 직행 URL + relay_url 보존",
   _items[0]["url"] == "https://reuters.com/world/story-1"
   and _items[0]["relay_url"].startswith("https://news.google.com/"))
ok("해소 실패 건은 중계 링크 유지",
   any(it["url"].startswith("https://news.google.com/") for it in _items))
ok("해소로 겹친 직접 피드 중복 제거", len(_items) == 2)

# --- (b) attach_sources: 출처 2개 → 3개 확장 --------------------------------
from draft import attach_sources

_SNAP_ITEMS = [
    {"source": "TechCrunch AI", "kind": "news",
     "title": "NebulaCore unveils QuantumLeap chip for AI servers",
     "url": "https://techcrunch.com/nebulacore-quantumleap",
     "summary": "NebulaCore QuantumLeap chip ships next quarter.",
     "published": "2026-11-25T01:00+09:00"},
    {"source": "The Verge AI", "kind": "news",
     "title": "NebulaCore QuantumLeap chip aims at AI server market",
     "url": "https://www.theverge.com/nebulacore-quantumleap",
     "summary": "QuantumLeap promises faster inference.",
     "published": "2026-11-25T02:00+09:00"},
    {"source": "Ars Technica", "kind": "news",
     "title": "QuantumLeap benchmarks show strong gains for NebulaCore",
     "url": "https://arstechnica.com/nebulacore-benchmarks",
     "summary": "Independent benchmarks of QuantumLeap.",
     "published": "2026-11-25T03:00+09:00"},
    {"source": "BleepingComputer", "kind": "news",
     "title": "Unrelated ransomware gang hits hospital chain",
     "url": "https://www.bleepingcomputer.com/ransomware-hospital",
     "summary": "Ransomware incident at a hospital chain.",
     "published": "2026-11-25T04:00+09:00"},
]
_SNAP = {"date": "2026-11-25", "items": _SNAP_ITEMS}
_BODY = ("NebulaCore가 QuantumLeap 칩을 공개했습니다. QuantumLeap은 AI 서버 "
         "시장을 겨냥하며 다음 분기에 출하됩니다. 업계는 QuantumLeap의 "
         "추론 성능에 주목하고 있습니다.")


def _issue_with(urls):
    return {"analysis": [{
        "id": "nebulacore",
        "title": "NebulaCore QuantumLeap 칩 공개",
        "body": [_BODY],
        "bullets": [_BODY],
        "takeaway": "QuantumLeap의 출하 일정이 중요합니다. 다음 분기 공시를 확인하면 됩니다.",
        "sources": [{"url": u} for u in urls],
    }]}


_out = attach_sources(_issue_with([
    "https://techcrunch.com/nebulacore-quantumleap",
    "https://www.theverge.com/nebulacore-quantumleap",
]), _SNAP)
_srcs = _out["analysis"][0]["sources"]
ok("출처 2개 기사에 같은 이야기 3번째 매체가 붙어 3개",
   len(_srcs) == 3 and any("arstechnica" in s["url"] for s in _srcs))
ok("무관한 기사는 붙지 않음",
   all("ransomware" not in s["url"] for s in _srcs))

_out1 = attach_sources(_issue_with([
    "https://techcrunch.com/nebulacore-quantumleap",
]), _SNAP)
ok("출처 1개 기사도 그룹 보충 + 엄격 보충으로 최대 3개",
   len(_out1["analysis"][0]["sources"]) == 3)

# 그룹이 쪼개진 경우(1차 풀 없음): 엄격 패스는 진입 1개 → 2개 상한 유지
_FRAG_SNAP = {"date": "2026-11-25", "items": [
    {"source": "TechCrunch AI", "kind": "news",
     "title": "NebulaCore unveils QuantumLeap chip for AI servers",
     "url": "https://techcrunch.com/nq-chip",
     "summary": "QuantumLeap chip.", "published": "2026-11-25T01:00+09:00"},
    {"source": "Ars Technica", "kind": "news",
     "title": "Inside the QuantumLeap architecture: cache design notes",
     "url": "https://arstechnica.com/nq-arch",
     "summary": "QuantumLeap architecture.", "published": "2026-11-25T02:00+09:00"},
    {"source": "Ars Technica", "kind": "news",
     "title": "QuantumLeap roadmap leak: packaging partners named",
     "url": "https://arstechnica.com/nq-roadmap",
     "summary": "QuantumLeap roadmap.", "published": "2026-11-25T03:00+09:00"},
]}
_out2 = attach_sources(_issue_with(["https://techcrunch.com/nq-chip"]),
                       _FRAG_SNAP)
ok("쪼개진 그룹에서는 엄격 패스 상한 2개 유지",
   len(_out2["analysis"][0]["sources"]) == 2)

# --- 영어 단위 환산 ----------------------------------------------------------
from draft import convert_english_units, convert_issue_units
from validate import _canon_num
from draft import NUM_RE, normalize_num_text


def _mags(text: str) -> set:
    return {_canon_num(m.group(0))
            for m in NUM_RE.finditer(normalize_num_text(text or ""))}


_CONVERT_CASES = [
    ("7.5B 달러에 기술 확보", "75억 달러에 기술 확보"),
    ("아마존이 $7.5B에 확보했다", "아마존이 75억 달러에 확보했다"),
    ("매출 40 billion 달러", "매출 400억 달러"),
    ("사용자 350 million 명", "사용자 3억 5,000만 명"),
    ("시장 $2.5 trillion 수준", "시장 2조 5,000억 달러 수준"),
    ("$350M 규모 투자", "3억 5,000만 달러 규모 투자"),
    ("70B 파라미터 모델", "700억 파라미터 모델"),
    ("5B 토큰 학습", "50억 토큰 학습"),
    ("80 billion won 계약", "800억 원 계약"),
    ("900 thousand 명 증가", "90만 명 증가"),
    ("3M은 새 제품을 내놨다", "3M은 새 제품을 내놨다"),
    ("GPT-5와 Claude 4.5 출시", "GPT-5와 Claude 4.5 출시"),
    ("가격 30% 인하, 응답 2배", "가격 30% 인하, 응답 2배"),
    ("`GPT-70B`와 70B 모델", "`GPT-70B`와 700억 모델"),
]
for _src, _want in _CONVERT_CASES:
    _got = convert_english_units(_src)
    ok(f"환산: {_src[:24]}", _got == _want)
    # 크기 보존: 변환 전후 수치 canon 집합이 같거나, 복합수 전개로
    # 게이트 추출에서 빠지는 경우(기존 P20 동작)만 허용한다.
    _before, _after = _mags(_src), _mags(_got)
    ok(f"크기 보존: {_src[:24]}", _after <= _before or _before == _after)

_issue = {"analysis": [{"title": "7.5B 달러 인수",
                        "bullets": ["40 billion 규모"],
                        "body": ["350 million 사용자를 확보했다"],
                        "takeaway": "규모가 중요합니다. 확인하면 됩니다.",
                        "sources": [{"url": "https://example.com/x"}]}],
          "briefing": [{"headline": "$350M 투자 유치", "summary": "요약"}]}
_conv = convert_issue_units(_issue)
ok("convert_issue_units: 제목 환산",
   _conv["analysis"][0]["title"] == "75억 달러 인수")
ok("convert_issue_units: 출처 URL 불변",
   _conv["analysis"][0]["sources"][0]["url"] == "https://example.com/x")

# --- UNIT-EN 피드백 코드 ------------------------------------------------------
from validate import collect_structured_errors

_res = collect_structured_errors(
    {"briefing": [], "analysis": [{
        "id": "x", "title": "40 billion 달러 시장",
        "body": ["본문입니다"], "bullets": [], "takeaway": "",
        "sources": [{"url": "https://example.com/a"}]}]},
    None)
ok("UNIT-EN 코드 수집", any(e.get("code") == "UNIT-EN" for e in _res))
_res2 = collect_structured_errors(
    {"briefing": [], "analysis": [{
        "id": "x", "title": "400억 달러 시장",
        "body": ["본문입니다"], "bullets": [], "takeaway": "",
        "sources": [{"url": "https://example.com/a"}]}]},
    None)
ok("환산된 텍스트에는 UNIT-EN 없음",
   not any(e.get("code") == "UNIT-EN" for e in _res2))

print(f"P31 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
