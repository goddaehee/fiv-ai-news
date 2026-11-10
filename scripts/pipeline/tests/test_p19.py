#!/usr/bin/env python3
"""P19 회귀 테스트: draft 발행 확정 + 출처 신뢰 표시 정상화.

배경 (4차 패널 평가, 6.3점):
1. 발행된 호가 draft:true인 채로 라이브에 서빙됐다. draft.py는 항상
   draft:true로 쓰고, 어느 단계도 뒤집지 않았다. -> run.py가 validate
   통과 시점에 finalize_publish로 draft:false를 보장하고, 프론트
   (data/news.ts)는 draft 호를 목록에서 제외하는 이중 방어.
2. 출처 15개 전부 kind:doc이라 모든 분석에 "1차 출처 포함" 배지가 붙고,
   라벨은 "Anthropic GNews" 같은 피드명이었다 (Codex P0).
   -> collect가 <source> 텍스트(발행처 이름)를 저장하고, draft.source_entry가
   라벨("Reuters · reuters.com")과 kind(중계=news)를 결정적으로 교정.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collect
import run
from draft import attach_sources, published_lock, source_entry
from validate import check

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


RELAY_URL = "https://news.google.com/rss/articles/CBMiTESTTOKEN?oc=5"

# ---------- 1. collect: <source> 발행처 이름 저장 ----------
RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News</title>
<item>
  <title>Chip probe widens to suppliers</title>
  <link>https://news.google.com/rss/articles/CBMiTESTTOKEN?oc=5</link>
  <description>Probe summary</description>
  <pubDate>Tue, 10 Nov 2026 01:00:00 GMT</pubDate>
  <source url="https://www.reuters.com">Reuters</source>
</item>
<item>
  <title>Direct post with no source element</title>
  <link>https://example.org/post</link>
  <description>AI model release summary</description>
  <pubDate>Tue, 10 Nov 2026 02:00:00 GMT</pubDate>
</item>
</channel></rss>"""

items = collect.parse_feed(RSS, "Anthropic GNews", "news")
ok("collect: GNews 아이템 수집", len(items) == 2)
ok("collect: publisher 이름 저장", items[0].get("publisher") == "Reuters")
ok("collect: origin_url 저장", items[0].get("origin_url") == "https://www.reuters.com")
ok("collect: source 없으면 publisher 없음", "publisher" not in items[1])

# ---------- 2. FEEDS kind 배정 ----------
feed_kinds = {name: kind for name, _url, kind in collect.FEEDS}
ok("feeds: TechCrunch는 news", feed_kinds.get("TechCrunch AI") == "news")
ok("feeds: GNews는 news", feed_kinds.get("Anthropic GNews") == "news"
   and feed_kinds.get("Google News AI") == "news")
ok("feeds: 공식 블로그는 doc", feed_kinds.get("OpenAI News") == "doc"
   and feed_kinds.get("Anthropic News") == "doc")
ok("feeds: HN은 talk", feed_kinds.get("HN AI") == "talk")

# ---------- 3. source_entry: 라벨·kind 교정 ----------
relay = {"source": "Anthropic GNews", "kind": "doc", "url": RELAY_URL,
         "origin_url": "https://www.reuters.com", "publisher": "Reuters"}
e = source_entry(relay)
ok("entry: 중계 라벨은 발행처 · 도메인", e["handle"] == "Reuters · reuters.com")
ok("entry: 중계 kind는 news로 강제", e["kind"] == "news")
ok("entry: origin_url 유지", e.get("origin_url") == "https://www.reuters.com")

relay_nopub = {"source": "Google News AI", "kind": "news", "url": RELAY_URL,
               "origin_url": "https://fortune.com"}
e = source_entry(relay_nopub)
ok("entry: 발행처 이름 없으면 도메인만", e["handle"] == "fortune.com")
ok("entry: 발행처 없어도 kind는 news", e["kind"] == "news")

relay_bare = {"source": "Google News AI", "kind": "doc", "url": RELAY_URL}
e = source_entry(relay_bare)
ok("entry: origin 없으면 피드명 유지하되 kind는 news",
   e["handle"] == "Google News AI" and e["kind"] == "news")

direct_doc = {"source": "OpenAI News", "kind": "doc",
              "url": "https://openai.com/news/post"}
e = source_entry(direct_doc)
ok("entry: 직행 공식은 doc + 피드명", e["kind"] == "doc" and e["handle"] == "OpenAI News")

direct_news = {"source": "TechCrunch AI", "kind": "news",
               "url": "https://techcrunch.com/2026/11/10/post"}
e = source_entry(direct_news)
ok("entry: 직행 언론은 news", e["kind"] == "news" and e["handle"] == "TechCrunch AI")

# ---------- 4. attach_sources 통합 ----------
snap = {"date": "2026-11-10", "items": [
    {"source": "Anthropic GNews", "kind": "news",
     "title": "Chip probe widens to suppliers", "url": RELAY_URL,
     "summary": "probe", "published": "2026-11-10T10:00:00+09:00",
     "origin_url": "https://www.reuters.com", "publisher": "Reuters"},
]}
issue = {"analysis": [{
    "id": "probe", "title": "1. Chip probe suppliers",
    "body": ["Chip probe widens to suppliers in the investigation."],
    "bullets": [], "takeaway": "", "tags": [],
    "sources": [{"url": RELAY_URL}],
}]}
attach_sources(issue, snap)
srcs = issue["analysis"][0]["sources"]
ok("attach: 출처 1개 조립", len(srcs) == 1)
ok("attach: 라벨 교정", srcs[0]["handle"] == "Reuters · reuters.com")
ok("attach: kind 교정", srcs[0]["kind"] == "news")

# ---------- 5. validate SRC-RELAY-KIND 게이트 ----------
def _issue_with_source(src):
    return {"date": "2026-11-10", "analysis": [{
        "id": "a", "title": "t", "bullets": ["b1", "b2"], "body": ["본문"],
        "takeaway": "판단 문장입니다. 다음 행동을 확인하면 됩니다. 추가 문장으로 길이를 맞춥니다.",
        "tags": [], "sources": [src]}]}

bag = check(_issue_with_source(
    {"handle": "Anthropic GNews", "url": RELAY_URL, "kind": "doc"}))
ok("validate: 중계+doc은 SRC-RELAY-KIND 에러",
   any("SRC-RELAY-KIND" in e for e in bag))
bag = check(_issue_with_source(
    {"handle": "Reuters · reuters.com", "url": RELAY_URL, "kind": "news",
     "origin_url": "https://www.reuters.com"}))
ok("validate: 중계+news는 게이트 통과",
   not any("SRC-RELAY-KIND" in e for e in bag))

# ---------- 6. finalize_publish ----------
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "issue.json"
    p.write_text(json.dumps({"date": "2026-11-10", "draft": True}),
                 encoding="utf-8")
    ok("finalize: draft:true를 뒤집음", run.finalize_publish(p) is True)
    ok("finalize: 값은 false", json.loads(p.read_text())["draft"] is False)
    ok("finalize: 이미 false면 무변경", run.finalize_publish(p) is False)

    p2 = Path(td) / "hand.json"
    p2.write_text(json.dumps({"date": "2026-09-01"}), encoding="utf-8")
    ok("finalize: 키 없는 호는 손대지 않음", run.finalize_publish(p2) is False)
    ok("finalize: 키가 생기지 않음", "draft" not in json.loads(p2.read_text()))

# ---------- 7. published_lock 의미 (AGENTS.md: 키 없음 = 잠금) ----------
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "i.json"
    p.write_text(json.dumps({"date": "2026-09-01"}), encoding="utf-8")
    ok("lock: draft 키 없음 = 잠금 (손편집 호)", published_lock(p) is True)
    p.write_text(json.dumps({"draft": True}), encoding="utf-8")
    ok("lock: draft:true = 잠금 아님", published_lock(p) is False)
    p.write_text(json.dumps({"draft": False}), encoding="utf-8")
    ok("lock: draft:false(발행 확정) = 재발행 허용", published_lock(p) is False)
    ok("lock: 파일 없음 = 잠금 아님",
       published_lock(Path(td) / "none.json") is False)

# ---------- 8. 발행본 데이터 불변식 (정규화 가드) ----------
issues_dir = Path(__file__).resolve().parents[3] / "content" / "issues"
bad_draft, bad_relay, bad_label = [], [], []
for f in sorted(issues_dir.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("draft") is True:
        bad_draft.append(f.name)
    for a in d.get("analysis", []):
        for s in a.get("sources", []):
            from urllib.parse import urlparse
            if (urlparse(s.get("url") or "").hostname or "") == "news.google.com":
                if s.get("kind") == "doc":
                    bad_relay.append((f.name, s.get("handle")))
                if "GNews" in str(s.get("handle") or ""):
                    bad_label.append((f.name, s.get("handle")))
ok("데이터: draft:true인 호 없음", not bad_draft)
ok("데이터: 중계+doc 출처 없음", not bad_relay)
ok("데이터: GNews 피드명 라벨 없음", not bad_label)

print(f"P19 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
