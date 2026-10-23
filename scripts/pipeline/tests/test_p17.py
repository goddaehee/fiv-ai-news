#!/usr/bin/env python3
"""P17 회귀 테스트: 톱뉴스 강제 편입(MUST-COVER) + 이미지 디스크 복원
+ 출처 밀도 회복(같은 이야기 보충) + 불릿 병합 비문(BODY-FRAG).

배경 (실측, 2026-10-23호 + 3차 패널 평가 5.9점):
- 이미지 증발 재발: 파일 4장이 public/img/2026-10-23/에 있는데 발행 JSON은
  0장. preserve_images는 이전 JSON 등록분만 이관해, 한 번 탈락한 이미지는
  복원 경로가 없었다. → restore_images_from_disk (메타+파일 스캔).
- php2shell(CVSS 9.2)이 원본 1번 분석인데 클론에는 0회. P16 coverage 신호는
  페이로드 정렬까지만 바꿔 최종 선택에서 또 탈락했다.
  → cluster.must_cover_stories + MUST-COVER 게이트 + 피드백.
- 출처 밀도 후퇴: P16 패딩 금지의 반대급부로 분석당 1.0개 (원본 6.8개).
  → attach_sources가 같은 이야기의 다른 매체 아이템을 보충.
- 불릿 강제 병합 비문: 분석 5개 중 3개의 본문 말미에 불릿이 마침표 없이
  이어붙음 (thicken_body 병합). → 병합 제거 + BODY-FRAG 게이트.
픽스처는 실측 제목·문장을 축약한 것이다.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cluster import must_cover_stories
from draft import (
    attach_sources,
    render_feedback,
    restore_images_from_disk,
    thicken_body,
    _ref_table,
)
from validate import (
    body_fragment_findings,
    check_quality,
    collect_structured_errors,
    must_cover_findings,
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


def _it(source, title, url, origin=None, published="2026-10-23T09:00:00+09:00",
        summary=""):
    d = {"source": source, "kind": "doc", "title": title, "url": url,
         "summary": summary, "published": published}
    if origin:
        d["origin_url"] = origin
    return d


# --- 1. must_cover_stories: 신호 판정 ---------------------------------------

DUET = [
    _it("Anthropic GNews", "Claude Duet app is Anthropic's bet on agents - TechCrunch",
        "https://news.google.com/d1", "https://techcrunch.com"),
    _it("Anthropic GNews", "Anthropic Introduces Claude Duet: A New Agentic AI App - CNET",
        "https://news.google.com/d2", "https://www.cnet.com"),
    _it("Anthropic GNews", "Anthropic Joins the AI Agent Race With Claude Duet - NYT",
        "https://news.google.com/d3", "https://www.nytimes.com"),
    _it("Anthropic GNews", "Anthropic unveils Claude Duet AI agent app - Reuters",
        "https://news.google.com/d4", "https://www.reuters.com"),
    # 대표 토큰 유사도가 낮아 별도 그룹으로 쪼개지는 실제 사례 (Barron's 비교 기사)
    _it("Anthropic GNews", "How Anthropic's Claude Duet Differs From Meta Muse in the AI Agent Race - Barron's",
        "https://news.google.com/d5", "https://www.barrons.com"),
]
PHP = [
    _it("The Hacker News", "PHP Issues Emergency Patches for Two Critical PHP2Shell RCE Flaws",
        "https://thehackernews.com/php2shell", summary="php2shell rce"),
    _it("BleepingComputer", "PHP ships emergency patches for critical PHP2Shell flaws",
        "https://bleepingcomputer.com/php2shell", summary="php2shell"),
    _it("TechCrunch AI", "PHP2Shell: Two Unpatched Critical PHP RCE Flaws (CVSS 9.2)",
        "https://techcrunch.com/php2shell", summary="cvss 9.2"),
]
# 지역지 템플릿 공지 — coverage 5지만 'other' 버킷이라 톱뉴스가 아니다
CIVIL = [
    _it(f"Local {i}", f"{city} Gazette's Artificial Intelligence Policy",
        f"https://news.google.com/c{i}", f"https://local{i}.example.com")
    for i, city in enumerate(["Honolulu", "Springfield", "Riverton", "Lakeview", "Fairbanks"])
]
# 단독 보도 critical — 아이템 1개뿐이면 security 신호 대상이 아니다
LONE = [
    _it("The Hacker News", "Lone zero-day in ObscureTool exploited in the wild",
        "https://thehackernews.com/lone", summary="zero-day"),
]
ITEMS = DUET + PHP + CIVIL + LONE

mc = must_cover_stories(ITEMS)
titles = [m["title"] for m in mc]
ok("must-cover: Duet가 coverage 신호로 선정", any("Duet" in t for t in titles))
ok("must-cover: php2shell이 security 신호로 선정",
   any("PHP" in t and m["signal"] == "security" for m, t in zip(mc, titles)))
ok("must-cover: 지역지 템플릿 공지(other 버킷 cov 5)는 제외",
   not any("Artificial Intelligence Policy" in t for t in titles))
ok("must-cover: 단독 보도 critical(n=1)은 제외",
   not any("ObscureTool" in t for t in titles))

duet_mc = next(m for m in mc if "Duet" in m["title"])
ok("must-cover: Duet coverage는 매체 수(≥4)", duet_mc["coverage"] >= 4)
ok("must-cover: 쪼개진 그룹(Barron's)의 URL도 서명 확장으로 포함",
   "https://news.google.com/d5" in duet_mc["urls"])
php_mc = next(m for m in mc if "PHP" in m["title"])
ok("must-cover: php URL 집합은 php 아이템만",
   php_mc["urls"] == {it["url"] for it in PHP})

# --- 2. must_cover_findings: 편입 판정은 출처 URL ----------------------------

_by_url = {url_core(it["url"]): it for it in ITEMS}
iss_none = {"analysis": [{"id": "x", "sources": []}]}
f_none = must_cover_findings(iss_none, ITEMS)
ok("findings: 아무것도 인용 안 하면 Duet·php 둘 다 누락",
   len(f_none) == 2)
iss_duet = {"analysis": [{"id": "x", "sources": [{"url": "https://news.google.com/d2"}]}]}
f_duet = must_cover_findings(iss_duet, ITEMS)
ok("findings: Duet 아이템 인용 시 Duet은 편입, php만 누락",
   len(f_duet) == 1 and "PHP" in f_duet[0]["title"])
ok("findings: 스냅샷 없으면 판정 안 함",
   must_cover_findings(iss_none, None) == [] and must_cover_findings(iss_none, []) == [])

qerr, _ = check_quality(
    {"date": "2026-10-23", "briefing": [], "analysis": iss_none["analysis"],
     "keynums": [], "timeline": []},
    set(_by_url), None, "2026-10-23", _by_url)
ok("게이트: MUST-COVER 에러가 check_quality에 실림",
   any(e.startswith("MUST-COVER") for e in qerr))
serr = collect_structured_errors(
    {"briefing": [], "analysis": iss_none["analysis"]}, _by_url)
ok("sidecar: MUST-COVER 구조화 에러 수집",
   any(e.get("code") == "MUST-COVER" for e in serr))

# --- 3. BODY-FRAG 게이트 ------------------------------------------------------

FRAG_ISSUE = {"analysis": [
    {"id": "a", "body": [
        "정상적인 첫 문단입니다. 사실 관계를 정리했습니다.",
        "따져보는 눈이 그만큼 중요해질 전망입니다. 여러 매체가 동시에 다루며 경쟁 구도가 뚜렷해짐",
    ]},
    {"id": "b", "body": [
        "종결 부호가 없어도 종결어미로 끝나면 완결 문장입니다",
        "짧은 문단",
        "성사 시 비상장 기업 최고 기록 경신 전망",
    ]},
]}
fr = body_fragment_findings(FRAG_ISSUE)
ok("BODY-FRAG: 병합 비문 2건만 검출 (종결어미·짧은 문단은 통과)",
   len(fr) == 2 and fr[0]["analysis_id"] == "a" and fr[1]["analysis_id"] == "b")
ok("BODY-FRAG: 실제 10/23호 비문 꼬리 검출",
   body_fragment_findings({"analysis": [{"id": "v", "body": [
       "원칙이 다시 중요해지는 국면입니다. SD-WAN 전체를 좌우하는 중앙 관리 시스템이 표적"]}]}) != [])

qerr2, _ = check_quality(
    {"date": "2026-10-23", "briefing": [], "analysis": FRAG_ISSUE["analysis"],
     "keynums": [], "timeline": []},
    None, None, "2026-10-23", None)
ok("게이트: BODY-FRAG 에러가 check_quality에 실림",
   sum(1 for e in qerr2 if e.startswith("BODY-FRAG")) == 2)
serr2 = collect_structured_errors({"briefing": [], "analysis": FRAG_ISSUE["analysis"]}, None)
ok("sidecar: BODY-FRAG 구조화 에러 수집",
   any(e.get("code") == "BODY-FRAG" for e in serr2))

# --- 4. thicken_body: 불릿 병합 제거 ------------------------------------------

ok("thicken_body: 짧은 문단에 불릿을 이어붙이지 않음",
   thicken_body(["짧은 본문입니다."], ["뚜렷해짐"]) == ["짧은 본문입니다."])
ok("thicken_body: 문단 1개면 합성 문단을 만들지 않음",
   len(thicken_body(["문단 하나입니다."], ["불릿1", "불릿2"])) == 1)
ok("thicken_body: 빈 문단만 제거하고 순서는 유지",
   thicken_body(["첫째입니다.", "", "둘째입니다."], []) == ["첫째입니다.", "둘째입니다."])

# --- 5. attach_sources: 같은 이야기 보충 --------------------------------------

SNAP17 = {"items": [
    _it("TechCrunch AI", "Claude Duet app is Anthropic's bet on agents",
        "https://techcrunch.com/duet", summary="duet"),
    _it("CNET", "Anthropic Introduces Claude Duet: A New Agentic AI App",
        "https://www.cnet.com/duet", summary="duet"),
    _it("Reuters", "Anthropic unveils Claude Duet AI agent app",
        "https://www.reuters.com/duet", summary="duet"),
    _it("Canva News", "Canva adds new design features for marketing teams",
        "https://www.canva.com/news/design", summary="design"),
]}
ISS17 = {"analysis": [{
    "id": "claude-duet",
    "title": "1. Claude Duet 공개, 에이전트 앱 경쟁 본격화",
    "bullets": ["Anthropic이 Claude Duet을 공개했다"],
    "body": ["Anthropic이 Claude Duet을 공개했다. 에이전트 전용 앱이다."],
    "takeaway": "에이전트 앱 경쟁이 본격화되는 점이 중요합니다. 도입 전에 권한 구조를 확인하면 됩니다.",
    "sources": [{"url": "https://techcrunch.com/duet"}],
}]}
out17 = attach_sources(json.loads(json.dumps(ISS17)), SNAP17, ref_table=_ref_table(SNAP17))
urls17 = [s["url"] for s in out17["analysis"][0]["sources"]]
ok("보충: 같은 이야기 다른 매체가 출처로 추가됨",
   "https://www.cnet.com/duet" in urls17 and "https://www.reuters.com/duet" in urls17)
ok("보충: 다른 이야기(Canva)는 추가되지 않음",
   "https://www.canva.com/news/design" not in urls17)
ok("보충: 상한 4개 유지", len(urls17) <= 4)

# --- 6. restore_images_from_disk ----------------------------------------------

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "content" / "pipeline" / "images").mkdir(parents=True)
    (root / "public" / "img" / "2026-10-24").mkdir(parents=True)
    (root / "public" / "img" / "2026-10-24" / "uber-chatgpt-work-3d7e2a90.webp").write_bytes(b"x")
    (root / "public" / "img" / "2026-10-24" / "gone-story-12345678.webp").write_bytes(b"x")
    (root / "content" / "pipeline" / "images" / "2026-10-24-uber-chatgpt-work.json").write_text(
        json.dumps({"date": "2026-10-24", "analysis": "uber-chatgpt-work",
                    "title": "3. 기업 전사 도입의 새 사례",
                    "src": "/img/2026-10-24/uber-chatgpt-work-3d7e2a90.webp",
                    "alt": "사무실 일러스트"}, ensure_ascii=False),
        encoding="utf-8")
    issue17 = {"analysis": [
        {"id": "uber-chatgpt", "title": "3. 기업 전사 도입의 새 사례", "images": []},
        {"id": "other-topic", "title": "9. 다른 주제", "images": []},
        {"id": "has-image", "title": "1. 이미 있는 분석",
         "images": [{"src": "/img/2026-10-24/uber-chatgpt-work-3d7e2a90.webp"}]},
    ]}
    # has-image가 이미 그 src를 쓰고 있으므로 uber에는 복원되지 않아야 정상이나,
    # taken 처리 확인을 위해 has-image를 빼고 본 케이스를 따로 본다.
    issue17b = {"analysis": issue17["analysis"][:2]}
    n = restore_images_from_disk(issue17b, "2026-10-24", root)
    ok("복원: id가 바뀐 같은 이야기(uber-chatgpt-work→uber-chatgpt)에 이미지 재등록",
       n == 1 and issue17b["analysis"][0]["images"]
       and issue17b["analysis"][0]["images"][0]["src"].endswith("uber-chatgpt-work-3d7e2a90.webp"))
    ok("복원: 무관한 분석에는 붙이지 않음",
       not issue17b["analysis"][1].get("images"))
    n2 = restore_images_from_disk(issue17, "2026-10-24", root)
    ok("복원: 이미 참조 중인 src는 중복 복원 안 함", n2 == 0)

# --- 7. render_feedback: MUST-COVER · BODY-FRAG --------------------------------

with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
    json.dump({"errors": [
        {"code": "MUST-COVER", "title": "PHP Issues Emergency Patches for PHP2Shell",
         "coverage": 2, "signal": "security"},
        {"code": "BODY-FRAG", "analysis_index": 0, "analysis_id": "claude-duet",
         "paragraph_index": 3, "tail": "경쟁 구도가 뚜렷해짐"},
    ]}, tf, ensure_ascii=False)
    sidecar = tf.name
fb = render_feedback(sidecar)
ok("피드백: MUST-COVER가 빠진 이야기를 짚음", "PHP2Shell" in fb and "analysis" in fb)
ok("피드백: BODY-FRAG가 조각 문장을 짚음", "뚜렷해짐" in fb and "완전한 문장" in fb)

# --- 8. P17b: BODY-LENGTH 피드백 + 보충 쿼터 캡 --------------------------------

short_issue = {"briefing": [], "analysis": [
    {"id": "s1", "body": ["이 문단은 여든 자가 되지 않는 짧은 전망 문단입니다. 조금 짧습니다."],
     "sources": [{"url": "https://example.org/a"}]},
]}
serr3 = collect_structured_errors(short_issue, None)
bl = [e for e in serr3 if e.get("code") == "BODY-LENGTH"]
ok("BODY-LENGTH: 80자 미만 문단이 sidecar에 실림",
   len(bl) == 1 and bl[0]["length"] < 80 and bl[0]["analysis_id"] == "s1")
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
    json.dump({"errors": bl}, tf, ensure_ascii=False)
    sidecar3 = tf.name
ok("BODY-LENGTH: 피드백 렌더링", "80자 미만" in render_feedback(sidecar3))

# 보충 쿼터 캡: 같은 도메인(BC)이 전체 분석 절반까지만 보충으로 들어간다
def _story_pair(prod, feat_a, feat_b, slug):
    return [
        _it(f"{prod} Blog", f"{prod} {feat_a}", f"https://{slug}.dev/a",
            summary=feat_a),
        _it("BleepingComputer", f"{prod} {feat_b}",
            f"https://bleepingcomputer.com/{slug}", summary=feat_b),
    ]

SNAPQ = {"items":
         _story_pair("ZetaDB", "releases vector search for AI apps",
                     "vector search arrives for AI apps", "zetadb")
         + _story_pair("KodaBrowser", "adds agent mode for research",
                       "agent mode rolls out to researchers", "koda")
         + _story_pair("MiraChip", "unveils NPU for edge inference",
                       "NPU targets edge inference devices", "mira")
         + _story_pair("LumenCRM", "launches call summary automation",
                       "call summary automation goes live", "lumen")}
ISSQ = {"analysis": [
    {"id": f"a{i}", "title": f"{i}. {prod} 소식",
     "bullets": [f"{prod} 관련 핵심 사실"],
     "body": [f"{prod}가 새 기능을 공개했다. 관련 업계의 주목을 받고 있다."],
     "takeaway": "새 기능이 경쟁 구도를 바꾸는 점이 중요합니다. 도입 조건을 확인하면 됩니다.",
     "sources": [{"url": f"https://{slug}.dev/a"}]}
    for i, (prod, slug) in enumerate(
        [("ZetaDB", "zetadb"), ("KodaBrowser", "koda"),
         ("MiraChip", "mira"), ("LumenCRM", "lumen")], start=1)
]}
outq = attach_sources(json.loads(json.dumps(ISSQ)), SNAPQ, ref_table=_ref_table(SNAPQ))
bc_counts = [sum(1 for s in a["sources"] if "bleepingcomputer" in s["url"])
             for a in outq["analysis"]]
ok("보충 쿼터 캡: BC 보충은 분석 절반(2개)까지만",
   bc_counts == [1, 1, 0, 0])
ok("보충 쿼터 캡: 캡에 걸린 분석은 1차 출처만 유지",
   all(len(a["sources"]) == 1 for a in outq["analysis"][2:]))

print(f"P17 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
