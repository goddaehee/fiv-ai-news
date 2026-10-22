#!/usr/bin/env python3
"""P10 회귀 테스트: 4자 패널 P0 8건 (10/21·10/22 연속 실패 원인 수정)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import _canon_num
from draft import (
    NUM_RE, normalize_num_text, number_mentions, SchemaError,
    normalize, attach_sources, _ref_table, render_feedback,
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


# --- P0-1: _canon_num 크기 기반 통일 ---
ok("canon $80B==800억==80 billion",
   _canon_num("$80B") == _canon_num("800억") == _canon_num("80 billion") == "mag:80000000000")
ok("canon 80억 != $80B (크기 다름 차단)", _canon_num("80억") != _canon_num("$80B"))
ok("canon 80억 == 8 billion", _canon_num("80억") == _canon_num("8 billion") == "mag:8000000000")
ok("canon 콤마 제거", _canon_num("$1,200M") == _canon_num("1.2B") == "mag:1200000000")
ok("canon $200 == 200달러", _canon_num("$200") == _canon_num("200달러") == "200")
ok("canon 5만 == 50000", _canon_num("5만") == "mag:50000")
ok("canon 3천 == 3000", _canon_num("3천") == "mag:3000")
ok("canon % 유지", _canon_num("30%") == "30%")
ok("canon 배 유지", _canon_num("2배") == "2배")
ok("canon 명 유지", _canon_num("100명") == "100명")
ok("canon 개 유지", _canon_num("400개") == "400개")
ok("canon 10x 유지", _canon_num("10x") == "10x")

# --- P0-4: NUM_RE S-1 lookbehind ---
ok("S-1: GPT-4 제외", not NUM_RE.search("GPT-4 출시"))
ok("S-1: v2배 제외", not NUM_RE.search("v2배 빨라짐"))
ok("S-1: a1개 제외", not NUM_RE.search("a1개 있음"))
ok("S-1: 70B 통과", bool(NUM_RE.search("70B 모델")))
ok("S-1: 30% 통과", bool(NUM_RE.search("30% 하락")))
ok("S-1: 하이픈 전처리 120-billion",
   "120 billion" in " ".join(number_mentions("open 120-billion-parameter model")))
ok("S-1: normalize_num_text GPT-4 유지", normalize_num_text("GPT-4") == "GPT-4")
ok("S-1: normalize_num_text 120-billion 변환",
   normalize_num_text("open 120-billion-parameter") == "open 120 billion-parameter")

# --- P0-3: ref 기반 결정적 소스 조립 ---
SNAP = {
    "date": "2026-10-22",
    "items": [
        {"title": "A사 모델 공개", "url": "https://blog.a.com/post1", "source": "A Blog",
         "summary": "A사가 80B 모델을 공개했다.", "kind": "doc"},
        {"title": "B사 분석", "url": "https://news.google.com/rss/articles/CBMix", "source": "B GNews",
         "summary": "B사가 분석했다.", "kind": "doc",
         "origin_url": "https://tech.example.org/b-analysis"},
        {"title": "중복 URL", "url": "https://blog.a.com/post1", "source": "A Blog dup",
         "summary": "중복", "kind": "doc"},
        {"title": "example 제외", "url": "https://example.com/x", "source": "X",
         "summary": "제외", "kind": "doc"},
    ],
}
table = _ref_table(SNAP)
ok("ref_table 중복 제거", len(table) == 2)
ok("ref_table 순서", table[0]["url"] == "https://blog.a.com/post1"
   and table[1]["url"] == "https://news.google.com/rss/articles/CBMix")

issue = {"analysis": [
    {"id": "a1", "title": "t", "sources": [{"ref": 0}, {"ref": 1}]},
    {"id": "a2", "title": "t", "sources": [{"ref": 99}]},  # 무효 ref → 제거
    {"id": "a3", "title": "t", "sources": [{"url": "https://blog.a.com/post1"}]},  # 구형 URL 호환
    {"id": "a4", "title": "t", "sources": []},  # hollow → 빈 채 (퍼지 매칭 금지)
]}
out = attach_sources(issue, SNAP)
ok("ref 0→URL", out["analysis"][0]["sources"][0]["url"] == "https://blog.a.com/post1")
ok("ref 1→URL + origin_url 유지",
   out["analysis"][0]["sources"][1]["url"] == "https://news.google.com/rss/articles/CBMix"
   and out["analysis"][0]["sources"][1]["origin_url"] == "https://tech.example.org/b-analysis")
ok("ref 1 handle", out["analysis"][0]["sources"][1]["handle"] == "B GNews")
ok("무효 ref 제거", out["analysis"][1]["sources"] == [])
ok("구형 URL 역조회", out["analysis"][2]["sources"][0]["url"] == "https://blog.a.com/post1")
ok("hollow 빈 채", out["analysis"][3]["sources"] == [])

# P10b: URL 기반 표기 (LLM이 실제로 쓰는 경로) — 테이블 역조회로 재조립
# 실제 파이프라인 흐름: normalize(_sources) → attach_sources
def _pipe(iss):
    n = normalize(iss, SNAP)
    return attach_sources(n, SNAP, ref_table=_ref_table(SNAP))

issue_u = {"briefing": [{"id": "b1", "headline": "H1", "summary": "S1"}],
    "analysis": [
    {"id": "b1", "title": "1. T", "bullets": ["b1", "b2"], "body": ["x" * 90, "y" * 90],
     "takeaway": "중요합니다. 확인하면 됩니다. " + "가" * 60, "tags": ["t1", "t2", "t3"],
     "sources": [
        {"url": "https://blog.a.com/post1", "handle": "A"},
        {"url": "https://news.google.com/rss/articles/CBMix", "handle": "B"}]},
    {"id": "b1", "title": "2. T", "bullets": ["b1", "b2"], "body": ["x" * 90, "y" * 90],
     "takeaway": "중요합니다. 확인하면 됩니다. " + "가" * 60, "tags": ["t1", "t2", "t3"],
     "sources": [{"url": "https://hallucinated.example.net/x"}]},  # 환각 URL → 버림
    {"id": "b1", "title": "3. T", "bullets": ["b1", "b2"], "body": ["x" * 90, "y" * 90],
     "takeaway": "중요합니다. 확인하면 됩니다. " + "가" * 60, "tags": ["t1", "t2", "t3"],
     "sources": ["https://blog.a.com/post1"]},  # 문자열 URL
], "keynums": [], "timeline": [], "tips": [{"title": "t", "body": "b", "via": ""}],
    "keywords": ["a", "b", "c"]}
out_u = _pipe(issue_u)
ok("URL 역조회 재조립", out_u["analysis"][0]["sources"][0]["url"] == "https://blog.a.com/post1")
ok("URL origin_url 유지",
   out_u["analysis"][0]["sources"][1].get("origin_url") == "https://tech.example.org/b-analysis")
ok("환각 URL 버림", out_u["analysis"][1]["sources"] == [])
ok("문자열 URL 처리", out_u["analysis"][2]["sources"][0]["url"] == "https://blog.a.com/post1")

# --- P0-5: keynums 폴백 수집 전체 확장 ---
snap_nums = {"date": "2026-10-22", "items": [
    {"title": "t1", "url": "https://x.com/1", "source": "S1", "summary": "가격이 30% 내리고 2배 빨라졌다."},
    {"title": "t2", "url": "https://x.com/2", "source": "S2", "summary": "사용자 100명 돌파."},
]}
iss = {"briefing": [
    {"id": "b1", "headline": "헤드라인 하나", "summary": "요약 내용 하나"},
    {"id": "b2", "headline": "헤드라인 둘", "summary": "요약 내용 둘"},
], "analysis": [], "keynums": [], "tips": [{"title": "t", "body": "b", "via": ""}],
    "timeline": [], "keywords": ["a", "b", "c"]}
n = normalize(iss, snap_nums)
ok("keynums 수집에서 3개", len(n["keynums"]) >= 3)
vals = {k["val"] for k in n["keynums"]}
ok("keynums 30% 포함", any("30%" in v for v in vals))
ok("keynums 100명 포함", any("100명" in v for v in vals))

# --- P0-7: summary 폴백 제거 + SchemaError ---
iss2 = {"briefing": [
    {"id": "b1", "headline": "헤드라인 하나", "summary": ""},  # summary 누락
], "analysis": [], "keynums": [], "tips": [{"title": "t", "body": "b", "via": ""}],
    "timeline": [], "keywords": ["a", "b", "c"]}
try:
    normalize(iss2, snap_nums)
    ok("summary 누락 시 SchemaError", False)
except SchemaError as e:
    ok("summary 누락 시 SchemaError", "summary 누락" in str(e))

# render_feedback SCHEMA-001
import json, tempfile
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump({"errors": [{"code": "SCHEMA-001", "message": "briefing[1]: summary 누락"}]}, f)
    fp = f.name
fb = render_feedback(Path(fp))
ok("feedback SCHEMA-001 렌더링", "스키마 오류" in fb and "summary 누락" in fb)

# --- P10c: SOURCES-MISSING 피드백 ---
from validate import collect_structured_errors
iss_sm = {"analysis": [
    {"id": "x1", "title": "t", "bullets": ["b"], "body": ["x" * 90, "y" * 90],
     "takeaway": "중요합니다. 확인하면 됩니다. " + "가" * 60, "sources": []},
    {"id": "x2", "title": "t", "bullets": ["b"], "body": ["x" * 90, "y" * 90],
     "takeaway": "중요합니다. 확인하면 됩니다. " + "가" * 60,
     "sources": [{"url": "https://blog.a.com/post1"}]},
]}
errs = collect_structured_errors(iss_sm, None)
sm = [e for e in errs if e.get("code") == "SOURCES-MISSING"]
ok("SOURCES-MISSING 1건", len(sm) == 1 and sm[0]["analysis_id"] == "x1")

import json as _json, tempfile as _tf
with _tf.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    _json.dump({"errors": [{"code": "SOURCES-MISSING", "analysis_index": 0, "analysis_id": "x1"}]}, f)
    fp3 = f.name
fb3 = render_feedback(Path(fp3))
ok("feedback SOURCES-MISSING 렌더링", "sources가 비어 있습니다" in fb3 and "x1" in fb3)

# --- P0-2: 피드백 문구 (한국어 표기 허용) ---
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump({"errors": [{"code": "NUMBERS-UNGROUNDED", "analysis_index": 0,
                           "analysis_id": "a1", "fields": ["body"], "domains": ["a.com"],
                           "allowed_raw": ["$80B"]}]}, f)
    fp2 = f.name
fb2 = render_feedback(Path(fp2))
ok("feedback 한국어 표기 허용 문구", "값이 같은 한국어 표기를 써도 됩니다" in fb2 and "$80B" in fb2)

print(f"\n{__name__}: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
