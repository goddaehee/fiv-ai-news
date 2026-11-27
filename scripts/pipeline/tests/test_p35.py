#!/usr/bin/env python3
"""P35 회귀 테스트: 보안 교차보도 피드 (Google News Security).

배경 (실측, 2026-11-24호 + run 45329507218 수집 스냅샷 234건):
- 출처 평균 1.83 (목표 2.5). KEPCO 유출·Decart 인수 분석이 각 1개 출처.
- KEPCO는 스냅샷 전체에 BleepingComputer 1건뿐이었다. Google News AI
  쿼리("artificial intelligence OR LLM")에는 보안 이야기가 안 걸리고,
  보안 전문 피드 2곳 중 THN은 KEPCO를 싣지 않았다 — 수집 단계에서
  교차보도가 불가능한 구조였다.
- 같은 날 피드를 직접 재어 보니 Security 피드 쿼리
  (data breach OR ransomware OR cyberattack)에는 같은 KEPCO 유출을
  다룬 SecurityWeek·Yahoo 기사가 있었다. 이 피드를 추가하면 보안
  이야기의 출처가 수집 단계부터 2~3개로 늘어난다.
- AI 쿼리를 "AI"까지 넓히는 안은 실측에서 기각: when:2d로 재어도
  Decart·KEPCO·GL.iNet이 0건이었고, 상위 100건이 일반 AI 뉴스로
  채워져 오히려 어제 이야기가 밀려났다. 쿼리는 좁게 유지한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collect import FEEDS, FEED_LIMITS, parse_feed
from cluster import story_groups

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# --- 피드 등록 -------------------------------------------------------------
_feed = {name: (url, kind) for name, url, kind in FEEDS}
ok("Google News Security 피드 등록",
   "Google News Security" in _feed)
_url, _kind = _feed.get("Google News Security", ("", ""))
ok("kind는 news", _kind == "news")
ok("Google News RSS 쿼리",
   _url.startswith("https://news.google.com/rss/search?q="))
ok("쿼리에 data breach 포함", "data+breach" in _url)
ok("쿼리에 ransomware 포함", "ransomware" in _url)
ok("쿼리에 cyberattack 포함", "cyberattack" in _url)
ok("수집 창은 1일 (AI 피드와 동일)", "when:1d" in _url)
ok("상한 100 (AI 피드와 동일)",
   FEED_LIMITS.get("Google News Security") == 100)
ok("피드 이름 중복 없음",
   len([n for n, _, _ in FEEDS]) == len({n for n, _, _ in FEEDS}))

# --- parse_feed: Google News 이름이면 힌트 필터 없이 수집 -------------------
_SEC_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News Security</title>
<item>
  <title>City water utility confirms data breach affecting 20000 residents</title>
  <link>https://news.google.com/rss/articles/CBMiXmh0dHBzOi8vd3d3LnNlY3VyaXR5d2Vlay5jb20vYQ?oc=5</link>
  <source url="https://www.securityweek.com/">SecurityWeek</source>
  <pubDate>Tue, 24 Nov 2026 05:00:00 GMT</pubDate>
  <description>A city water utility confirmed a data breach.</description>
</item>
</channel></rss>"""
_sec_items = parse_feed(_SEC_XML, "Google News Security", "news")
ok("AI 힌트 없는 보안 기사도 수집 (이름 규칙)",
   len(_sec_items) == 1)
ok("origin_url 저장",
   _sec_items and _sec_items[0].get("origin_url") == "https://www.securityweek.com/")
ok("publisher 저장",
   _sec_items and _sec_items[0].get("publisher") == "SecurityWeek")

# --- 교차보도: 11-24 KEPCO 실측 제목 3건이 한 그룹, coverage 3 ------------
_kepco = [
    {"source": "BleepingComputer", "kind": "news",
     "title": "South Korea's power giant KEPCO confirms data breach impacting 1.5 million",
     "url": "https://www.bleepingcomputer.com/news/security/south-koreas-power-giant-kepco-confirms-data-breach-impacting-1-5-million/",
     "summary": "", "published": None},
    {"source": "Google News Security", "kind": "news",
     "title": "1.5 Million Impacted by Data Breach at South Korean Electric Company KEPCO",
     "url": "https://news.google.com/rss/articles/CBMiXmh0dHBzOi8vd3d3LnNlY3VyaXR5d2Vlay5jb20vYQ?oc=5",
     "origin_url": "https://www.securityweek.com/",
     "summary": "", "published": None},
    {"source": "Google News Security", "kind": "news",
     "title": "South Korean power giant confirms data breach - KEPCO says incident affected 1.5 million people",
     "url": "https://news.google.com/rss/articles/CBMiXmh0dHBzOi8veWFob28uY29tL2E?oc=5",
     "origin_url": "https://www.yahoo.com/",
     "summary": "", "published": None},
]
_groups = story_groups(_kepco)
_cov = {it["url"]: g["coverage"] for g in _groups for it in g["items"]}
ok("KEPCO 3건이 한 그룹", len(_groups) == 1)
ok("KEPCO coverage 3 (매체 3곳)",
   all(_cov[u] == 3 for u in _cov))
ok("무관한 보안 기사는 별도 그룹",
   len(story_groups(_kepco + [
       {"source": "Google News Security", "kind": "news",
        "title": "Teachers On Reserve Data Breach Reported; Attorneys Investigate Claims",
        "url": "https://news.google.com/rss/articles/CBMiXmh0dHBzOi8veWFob28uY29tL2I?oc=5",
        "origin_url": "https://www.yahoo.com/",
        "summary": "", "published": None},
   ])) == 2)

print(f"P35 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
