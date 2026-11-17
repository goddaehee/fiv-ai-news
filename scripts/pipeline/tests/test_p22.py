#!/usr/bin/env python3
"""P22 회귀 테스트: 출처 라벨·보충 (5차 평가 P4).

(a) ArticleView origin_url 조건부 우선 — TSX라 단위 테스트 불가, 렌더는
    수동 확인(가드: 경로 없는 origin_url이면 s.url 유지).
(b) source_entry 집계자 분기 — HN AI / Hacker News 피드의 외부 매체 링크는
    URL 도메인 기준으로 라벨·kind 교정. "The Hacker News"는 제외(정확 일치).
(c) SOURCES-THIN 피드백 + 2차 보충 + payload 2개 대표 + score_bucket 매체수.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import collect_structured_errors, check_source_relevance, url_core
from draft import source_entry, render_feedback, payload_items, attach_sources
from cluster import story_groups
from select_items import score_bucket

PASS = 0
FAIL = 0


def ok(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# --- (b) source_entry 집계자 분기 ---

def _it(source, url, kind="talk", publisher=None, origin_url=None):
    d = {"source": source, "url": url, "kind": kind}
    if publisher:
        d["publisher"] = publisher
    if origin_url:
        d["origin_url"] = origin_url
    return d


e1 = source_entry(_it("HN AI", "https://www.businessinsider.com/reddit-traffic-down-13-percent"))
ok("HN AI + 외부 URL → 도메인 라벨", e1["handle"] == "businessinsider.com")
ok("HN AI + 외부 URL → kind news", e1["kind"] == "news")

e2 = source_entry(_it("HN AI", "https://news.ycombinator.com/item?id=12345678"))
ok("HN AI + HN 토론 URL → talk 유지", e2["kind"] == "talk")
ok("HN AI + HN 토론 URL → 라벨 유지", e2["handle"] == "HN AI")

e3 = source_entry(_it("The Hacker News", "https://thehackernews.com/2026/11/x.html"))
ok("The Hacker News는 집계자 분기에 안 걸림", e3["handle"] == "The Hacker News")

e4 = source_entry(_it("Hacker News", "https://www.bleepingcomputer.com/news/security/x"))
ok("Algolia Hacker News + 외부 URL → 교정", e4["handle"] == "bleepingcomputer.com" and e4["kind"] == "news")

e5 = source_entry(_it("HN AI", "https://www.businessinsider.com/x", publisher="Business Insider"))
ok("publisher 있으면 '이름 · 도메인'", e5["handle"] == "Business Insider · businessinsider.com")

e6 = source_entry(_it("TechCrunch AI", "https://techcrunch.com/x", kind="news"))
ok("일반 피드 직행은 기존 동작 유지", e6["handle"] == "TechCrunch AI" and e6["kind"] == "news")

# SRC-REL-101이 "HN AI" 라벨을 잡는지 (경고 전용 감지)
rel_issue = {"analysis": [{"id": "a1", "title": "레딧 트래픽 감소",
                           "bullets": ["레딧 트래픽이 줄었다"],
                           "body": ["레딧 트래픽이 줄었습니다. 배경과 맥락을 설명합니다. 하지만 한계도 있습니다."],
                           "takeaway": "트래픽 변화를 주시하면 됩니다. 담당자는 이번 주 안에 검토하면 됩니다.",
                           "sources": [{"handle": "HN AI", "kind": "talk",
                                        "url": "https://www.businessinsider.com/x"}]}]}
holds, _ = check_source_relevance(rel_issue, None)
ok("SRC-REL-101이 HN AI 라벨 불일치 감지", any("SRC-REL-101" in h for h in holds))

# --- (c) SOURCES-THIN 수집 ---

def _collected_map(items):
    m = {}
    for it in items:
        m[url_core(it["url"])] = it
    return m


# 같은 이야기 2개 매체 (coverage=2): 제목 토큰이 겹쳐 한 그룹으로 묶여야 함
cov_items = [
    {"source": "BleepingComputer", "url": "https://www.bleepingcomputer.com/q9",
     "title": "NebulaCore quantum chip ships to data centers", "summary": "Q9 chip ships.", "kind": "news"},
    {"source": "TechCrunch AI", "url": "https://techcrunch.com/q9",
     "title": "NebulaCore quantum chip ships to data centers today", "summary": "Q9 chip ships today.", "kind": "news"},
]
cmap = _collected_map(cov_items)
groups = story_groups(cov_items)
ok("픽스처: 두 아이템이 한 그룹", len(groups) == 1 and groups[0]["coverage"] == 2)

thin_issue = {"date": "2026-11-16", "briefing": [],
              "analysis": [{"id": "q9", "title": "Q9 칩 출하",
                            "bullets": ["Q9 칩이 출하됐다"],
                            "body": ["Q9 칩이 데이터센터에 출하됐습니다. 배경과 맥락을 설명합니다. 하지만 한계도 있습니다."],
                            "takeaway": "Q9 칩 출하를 주시하면 됩니다. 담당자는 이번 주 안에 검토하면 됩니다.",
                            "sources": [{"handle": "BleepingComputer", "kind": "news",
                                         "url": "https://www.bleepingcomputer.com/q9"}]}]}
errs = collect_structured_errors(thin_issue, cmap)
thin = [e for e in errs if e.get("code") == "SOURCES-THIN"]
ok("coverage≥2인데 출처 1개 → SOURCES-THIN", len(thin) == 1 and thin[0].get("coverage") == 2)

# coverage=1 단독은 제외
solo_items = [{"source": "OpenAI News", "url": "https://openai.com/solo",
               "title": "OpenAI solo announcement today", "summary": "Solo.", "kind": "doc"}]
cmap_solo = _collected_map(solo_items)
solo_issue = {"date": "2026-11-16", "briefing": [],
              "analysis": [{"id": "solo", "title": "단독 발표",
                            "bullets": ["단독 발표가 있었다"],
                            "body": ["단독 발표가 있었습니다. 배경과 맥락을 설명합니다. 하지만 한계도 있습니다."],
                            "takeaway": "단독 발표를 주시하면 됩니다. 담당자는 이번 주 안에 검토하면 됩니다.",
                            "sources": [{"handle": "OpenAI News", "kind": "doc",
                                         "url": "https://openai.com/solo"}]}]}
errs_solo = collect_structured_errors(solo_issue, cmap_solo)
ok("coverage=1 doc 단독 → SOURCES-THIN 없음", not any(e.get("code") == "SOURCES-THIN" for e in errs_solo))

# render_feedback에 SOURCES-THIN 블록이 렌더링되는지
import json, tempfile
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump({"errors": [{"code": "SOURCES-THIN", "analysis_index": 0, "analysis_id": "q9", "coverage": 2}]}, f)
    sidecar = f.name
fb = render_feedback(sidecar)
ok("render_feedback에 SOURCES-THIN 처방", "SOURCES-THIN" not in fb and "q9" in fb and "2개 매체" in fb)

# --- (c) payload_items: coverage≥2 그룹은 대표 2개 ---

pl = payload_items(cov_items)
ok("coverage=2 그룹은 대표 2개 노출", len(pl) == 2)
ok("대표 2개 모두 coverage 2", all(c == 2 for _, c in pl))

pl_solo = payload_items(solo_items)
ok("coverage=1 그룹은 대표 1개", len(pl_solo) == 1)

# --- (c) score_bucket: 피드 라벨이 아니라 실발행처 수로 매체수 계산 ---

def _sitem(source, url, origin_url=None):
    d = {"title": "Anthropic IPO news today", "source": source, "url": url,
         "published": "2026-11-16T10:00:00+09:00", "summary": "x" * 60, "kind": "news"}
    if origin_url:
        d["origin_url"] = origin_url
    return d


sc1 = score_bucket([_sitem("Anthropic GNews", "https://news.google.com/a", "https://www.reuters.com"),
                    _sitem("Anthropic GNews", "https://news.google.com/b", "https://www.bloomberg.com")])
sc2 = score_bucket([_sitem("Anthropic GNews", "https://news.google.com/a", "https://www.reuters.com"),
                    _sitem("Anthropic GNews", "https://news.google.com/c", "https://www.reuters.com/x")])
ok("GNews 라벨이 같아도 매체 2곳이면 impact 1", sc1["impact"] == 1)
ok("같은 매체 2건이면 impact 0", sc2["impact"] == 0)

# --- (c) attach_sources 2차 패스: 쪼개진 그룹의 형제를 보충 ---

snap_items = [
    {"source": "BleepingComputer", "url": "https://www.bleepingcomputer.com/q9a",
     "title": "NebulaCore chip ships to data centers", "summary": "NebulaCore chip ships to centers.", "kind": "news"},
    {"source": "TechCrunch AI", "url": "https://techcrunch.com/q9b",
     "title": "NebulaCore benchmarks show strong gains", "summary": "NebulaCore benchmarks show gains.", "kind": "news"},
    {"source": "The Verge", "url": "https://www.theverge.com/unrelated",
     "title": "Smartphone battery life improves slightly", "summary": "Battery life improves.", "kind": "news"},
]
g2 = story_groups(snap_items)
ok("픽스처: Q9 두 아이템이 별도 그룹(쪼개짐)", len(g2) >= 2)
snap2 = {"items": snap_items}
issue2 = {"analysis": [{"id": "q9", "title": "Q9 칩 출하",
                        "bullets": ["Q9 칩이 출하됐다"],
                        "body": ["NebulaCore 칩이 데이터센터에 출하됐습니다. 배경과 맥락을 설명합니다. 하지만 한계도 있습니다. NebulaCore 벤치마크도 공개됐습니다."],
                        "takeaway": "Q9 칩 출하를 주시하면 됩니다. 담당자는 이번 주 안에 검토하면 됩니다.",
                        "sources": [{"url": "https://www.bleepingcomputer.com/q9a"}]}]}
out2 = attach_sources(issue2, snap2)
srcs2 = out2["analysis"][0]["sources"]
ok("2차 패스: 단일 출처가 2개로 보충", len(srcs2) == 2)
ok("2차 패스: 무관 아이템은 안 붙음",
   all("theverge.com" not in (s.get("url") or "") for s in srcs2))

print(f"P22 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
