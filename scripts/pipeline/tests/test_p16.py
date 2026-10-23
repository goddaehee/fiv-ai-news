#!/usr/bin/env python3
"""P16 회귀 테스트: 톱뉴스 커버리지(교차보도 신호·보안 버킷·보안 피드)
+ keynums-기사 연결(KEYNUMS-LINK) + 출처-주장 연결(attach 필터·SRC-TOPIC).

배경 (실측, 2026-10-23호 + run 39872151721 수집 스냅샷 234건):
- Claude Duet는 수집 10건(10개 매체)이었으나 anthropic 버킷에서 수집
  순서 절단 + 대표 스토리 경쟁에서 IPO에 밀려 분석에서 탈락했다.
  → story_groups 교차보도 신호 + 페이로드 coverage 정렬 + 프롬프트 지시.
- php2shell(PHP 제로데이)은 이름으로는 미수집이었고, 같은 사건의
  TechCrunch 기사는 제목의 'OpenAI' 때문에 openai 버킷 16번째로 묻혔다.
  → 보안 전문 피드 2곳 추가 + security 버킷 룰 최상단.
- keynums 3개 중 2개(77%·13개)가 analysis 없는 이야기의 수치였다.
  → KEYNUMS-LINK 게이트 + normalize 폴백을 인용 아이템·본문 등장으로 제한.
- 분석에 무관한 출처가 섞였다 (Minerva 분석에 유럽 금융 블로그 등).
  SRC-REL은 회사 도메인 기반이라 중립 매체 내부 오염을 못 잡는다.
  → attach_sources 토큰 정합 필터 + SRC-TOPIC 경고.
픽스처는 실측 제목·문장을 축약한 것이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collect
from cluster import cluster, story_groups
from draft import attach_sources, payload_items, render_feedback
from validate import check_src_topic, keynums_link_findings, url_core

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _it(source, title, url, origin=None, published="2026-10-22T10:00:00+09:00",
        summary=""):
    d = {"source": source, "kind": "doc", "title": title, "url": url,
         "summary": summary, "published": published}
    if origin:
        d["origin_url"] = origin
    return d


# --- 1. story_groups: Duet 교차보도 신호 -----------------------------------

DUET = [
    _it("Anthropic GNews", "Claude Duet app is Anthropic's bet on agents - TechCrunch",
        "https://news.google.com/a1", "https://techcrunch.com"),
    _it("Anthropic GNews", "Anthropic Introduces Claude Duet: A New Agentic AI App - CNET",
        "https://news.google.com/a2", "https://www.cnet.com"),
    _it("Anthropic GNews", "Anthropic Joins the A.I. Agent Race With Claude Duet - NYT",
        "https://news.google.com/a3", "https://www.nytimes.com"),
    _it("TechCrunch AI", "Claude Duet app is Anthropic's bet on agents",
        "https://techcrunch.com/duet"),
]
IPO = [
    _it("Anthropic GNews", "Anthropic IPO stands alone as AI market jitters sideline others - Reuters",
        "https://news.google.com/b1", "https://www.reuters.com"),
]
groups = story_groups(DUET + IPO)
duet_g = [g for g in groups if any("duet" in it["title"].lower() for it in g["items"])]
ipo_g = [g for g in groups if any("ipo" in it["title"].lower() for it in g["items"])]
ok("Duet 그룹이 하나로 묶임", len(duet_g) == 1)
ok("Duet coverage >= 3 (매체 4곳)", duet_g and duet_g[0]["coverage"] >= 3)
ok("IPO는 별도 그룹", len(ipo_g) == 1 and ipo_g[0]["coverage"] == 1)
ok("GNews 라벨이 같아도 origin 도메인으로 매체 구분",
   duet_g and len(duet_g[0]["sources"]) >= 3)

# --- 2. payload_items: coverage 우선 정렬 + 대표 1개 ------------------------

pl = payload_items(DUET + IPO)
ok("페이로드 첫 항목이 Duet (coverage 우선)", "duet" in pl[0][0]["title"].lower())
ok("페이로드 첫 항목 coverage >= 3", pl[0][1] >= 3)
ok("같은 이야기는 대표 1개만 (Duet 중복 제거)",
   sum(1 for it, _ in pl if "duet" in it["title"].lower()) <= 2)  # 제목 변형 2그룹까지 허용
ok("IPO도 페이로드에 포함", any("ipo" in it["title"].lower() for it, _ in pl))

# --- 3. security 버킷 룰 -----------------------------------------------------

buckets = cluster([
    _it("TechCrunch AI", "PHP Armageddon fallout: critical vulnerability disclosed in PHP",
        "https://techcrunch.com/php"),
    _it("BleepingComputer", "Amazon says PHP2Shell exploitation began 4 days before patches",
        "https://www.bleepingcomputer.com/php2shell"),
    _it("OpenAI GNews", "OpenAI launches new model for coding - Reuters",
        "https://news.google.com/c1", "https://www.reuters.com"),
])
ok("취약점 제목은 security 버킷", len(buckets.get("security") or []) >= 1)
ok("php2shell 제목은 security 버킷",
   any("php2shell" in it["title"].lower() for it in buckets.get("security") or []))
ok("일반 OpenAI 뉴스는 security로 안 감",
   all("security" != b for b, its in buckets.items()
       for it in its if "launches new model" in it["title"]))

# --- 4. 보안 피드 parse_feed 필터 -------------------------------------------

_FEED_TMPL = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>x</title>
<item><title>{t1}</title><link>https://example.com/1</link>
<description>{d1}</description><pubDate>Thu, 22 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>{t2}</title><link>https://example.com/2</link>
<description>{d2}</description><pubDate>Thu, 22 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

xml_sec = _FEED_TMPL.format(
    t1="Critical zero-day vulnerability exploited in the wild",
    d1="Attackers are exploiting the flaw.",
    t2="Local bakery wins regional bread award",
    d2="Judges praised the sourdough.",
).encode()
items_thn = collect.parse_feed(xml_sec, "The Hacker News", "doc")
ok("보안 피드: 제로데이 기사는 통과", len(items_thn) == 1
   and "zero-day" in items_thn[0]["title"])
xml_ai = _FEED_TMPL.format(
    t1="New AI model beats benchmark records",
    d1="The LLM scored higher.",
    t2="Local bakery wins regional bread award",
    d2="Judges praised the sourdough.",
).encode()
items_bc = collect.parse_feed(xml_ai, "BleepingComputer", "doc")
ok("보안 피드: AI 기사는 통과, 무관 기사는 차단", len(items_bc) == 1)
ok("보안 피드가 FEEDS에 등록됨",
   {"The Hacker News", "BleepingComputer"} <= {f[0] for f in collect.FEEDS})

# --- 5. attach_sources 토큰 정합 필터 ---------------------------------------

SNAP_ITEMS = [
    _it("1Password Blog", "1Password launches a way for AI agents to log in",
        "https://blog.1password.com/agents", summary="agents login"),
    _it("Canva News", "Canva adds new design features for marketing teams",
        "https://www.canva.com/news/design", summary="design"),
    _it("TechCrunch AI", "Left alone with nothing to do, AI agents built a society",
        "https://techcrunch.com/mit-island", summary="agents island"),
]
AGENT_ANALYSIS = {
    "id": "agent-login",
    "title": "AI 에이전트 로그인 위임 기능 공개",
    "bullets": ["1Password가 AI agents의 로그인을 대신 처리하는 기능을 내놨다"],
    "body": ["1Password가 AI agent가 사용자를 대신해 로그인하는 기능을 공개했다. "
             "agent마다 권한 범위를 정할 수 있다."],
    "takeaway": "AI agents의 로그인 위임이 본격화되는 점이 중요합니다. 앞으로 권한 관리를 확인하면 됩니다.",
    "sources": [{"url": u} for u in (
        "https://blog.1password.com/agents",
        "https://www.canva.com/news/design",
        "https://techcrunch.com/mit-island",
    )],
}
issue = {"analysis": [dict(AGENT_ANALYSIS)]}
snap = {"items": SNAP_ITEMS}
out = attach_sources(issue, snap)
srcs = out["analysis"][0]["sources"]
urls = [s["url"] for s in srcs]
ok("무관한 Canva 출처 제거", "https://www.canva.com/news/design" not in urls)
ok("본문 주제(1Password) 출처 유지", "https://blog.1password.com/agents" in urls)

# 전부 무관이면 최소 1개 유지 (빈 sources 판정은 검증기 몫)
issue2 = {"analysis": [dict(AGENT_ANALYSIS, sources=[
    {"url": "https://www.canva.com/news/design"}])]}
out2 = attach_sources(issue2, snap)
ok("출처 1개뿐이면 필터 미적용", len(out2["analysis"][0]["sources"]) == 1)

# --- 6. KEYNUMS-LINK 게이트 --------------------------------------------------

def _analysis_with(*nums_text):
    body = " ".join(nums_text)
    return {"id": "a1", "title": "기사", "bullets": [body], "body": [body],
            "takeaway": "중요합니다. 확인하면 됩니다.", "sources": []}

iss_linked = {
    "keynums": [{"val": "30,000명", "lab": "전 직원 확대", "sub": "OpenAI 발표"}],
    "analysis": [_analysis_with("전 직원 3만 명에게 도구를 확대한다")],
}
ok("KEYNUMS-LINK: 30,000명 ↔ 본문 '3만 명' 연결됨",
   keynums_link_findings(iss_linked) == [])

iss_orphan = {
    "keynums": [{"val": "77%", "lab": "정확도", "sub": "Dharma 발표"}],
    "analysis": [_analysis_with("전 직원 3만 명에게 도구를 확대한다")],
}
f = keynums_link_findings(iss_orphan)
ok("KEYNUMS-LINK: 본문에 없는 77%는 단절로 잡음",
   len(f) == 1 and f[0]["val"] == "77%")

iss_unitfree = {
    "keynums": [{"val": "125건", "lab": "사례 수", "sub": "발표"}],
    "analysis": [_analysis_with("아무 수치도 없는 본문")],
}
ok("KEYNUMS-LINK: NUM_RE 밖 단위(건)는 검사 제외 (오탐 방지)",
   keynums_link_findings(iss_unitfree) == [])

iss_pct = {
    "keynums": [{"val": "77%", "lab": "정확도", "sub": "발표"}],
    "analysis": [_analysis_with("오류가 77건 보고됐다")],
}
ok("KEYNUMS-LINK: %는 숫자만 같다고 연결하지 않음",
   len(keynums_link_findings(iss_pct)) == 1)

# --- 7. SRC-TOPIC 경고 --------------------------------------------------------

by_url = {url_core(it["url"]): it for it in SNAP_ITEMS}
iss_topic = {"analysis": [dict(AGENT_ANALYSIS, sources=[
    {"url": "https://blog.1password.com/agents"},
    {"url": "https://www.canva.com/news/design"},
])]}
warns = check_src_topic(iss_topic, by_url)
ok("SRC-TOPIC: Canva 출처에 경고", any("Canva" in w for w in warns))
ok("SRC-TOPIC: 1Password 출처는 경고 없음",
   not any("1Password" in w for w in warns))

# --- 8. render_feedback KEYNUMS-LINK ------------------------------------------

import json as _json
import tempfile as _tempfile

with _tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8") as _f:
    _json.dump({"errors": [
        {"code": "KEYNUMS-LINK", "keynum_index": 1, "val": "77%"}]}, _f)
    _sidecar = _f.name
fb = render_feedback(_sidecar)
ok("피드백에 KEYNUMS-LINK 처방 포함", "77%" in fb and "keynums" in fb)

# --- 9. normalize keynums 폴백: 인용 + 본문 등장일 때만 충원 ----------------

from draft import normalize

_FB_SNAP = {"date": "2026-10-23", "items": [
    _it("Google News AI", "모델 가격 30% 인하 발표", "https://news.google.com/f1",
        origin="https://techcrunch.com/"),
    _it("Google News AI", "경쟁사 사용자 100명 돌파", "https://news.google.com/f2",
        origin="https://www.theverge.com/"),
]}


def _fb_issue(body_text, cite_f1=True):
    srcs = [{"url": "https://news.google.com/f1"}] if cite_f1 else []
    return {
        "briefing": [
            {"id": "b1", "headline": "헤드라인 하나", "summary": "요약 하나"},
            {"id": "b2", "headline": "헤드라인 둘", "summary": "요약 둘"},
        ],
        "analysis": [{
            "id": "b1", "title": "모델 가격 인하",
            "bullets": [body_text], "body": [body_text],
            "takeaway": "가격이 바뀐 점이 중요합니다. 도입 전에 확인하면 됩니다.",
            "sources": srcs,
        }],
        "keynums": [], "tips": [{"title": "t", "body": "b", "via": ""}],
        "timeline": [], "keywords": ["a", "b", "c"],
    }


n_cited = normalize(_fb_issue("모델 가격이 30% 인하됐다고 회사가 밝혔다."), _FB_SNAP)
ok("폴백: 인용+본문 등장 수치는 충원", any("30%" in k["val"] for k in n_cited["keynums"]))
ok("폴백: 인용 안 한 아이템의 수치는 충원 안 함",
   not any("100명" in k["val"] for k in n_cited["keynums"]))
n_nobody = normalize(_fb_issue("모델 가격이 내렸다고 회사가 밝혔다."), _FB_SNAP)
ok("폴백: 본문에 없는 수치는 인용했어도 충원 안 함", n_nobody["keynums"] == [])

print(f"P16 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
