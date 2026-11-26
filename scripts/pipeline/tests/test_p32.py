#!/usr/bin/env python3
"""P32 회귀 테스트: 출처-주장 대조 강화 0~1단계.

0단계 (SRC-FEEDBACK): 기존 SRC-REL-001/101·SRC-TOPIC 판정을 재시도
피드백(sidecar collect_structured_errors + render_feedback)에 연결한다.
판정 로직은 그대로 — 게이트 문자열이 기존과 같은지도 함께 본다.

1단계 (SRC-ORPHAN-001): 붙은 출처가 어느 문장과도 희귀 토큰(제품명·
사건명)으로 겹치지 않으면 고립 출처로 판정한다 (warning + 피드백).

픽스처는 2026-11-26호 실측 사례 축약이다:
- 분석 1 (Drupal)에 GeoServer 결함 기사 부착 (유형 A)
- 분석 2 (팔로알토)에 Infratrust 공급망 기사 부착 (유형 A)
- 분석 3 (1Password)에 GitHub SHA 우회 기사 부착 (유형 B — 회사명만 겹침)
- 분석 4 (NuGet)에 Google 단일 비트 기사 부착 (유형 A)
- 분석 5 (OpenAI 통합)에 Benzinga Anthropic IPO 기사 부착 (유형 A —
  SRC-TOPIC은 openai 토큰 겹침으로 통과시키는 사례)
- 분석 6 (GPT-6)은 OpenAI 공식 출처 1개 — 정상 사례로 통과해야 한다.
스냅샷 채움 아이템은 회사명·일반어(hackers·github·openai)의 df를 올려
'흔한 토큰'이 되게 한다 (희귀도 임계 max(3, 5%) 기준).
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import PROMPT, render_feedback
from validate import (
    check_quality,
    check_source_relevance,
    collect_structured_errors,
    src_orphan_findings,
    src_rel_findings,
    src_topic_findings,
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


def _it(source, title, url, origin=None, published="2026-11-25T10:00:00+09:00",
        summary=""):
    d = {"source": source, "kind": "news", "title": title, "url": url,
         "summary": summary, "published": published}
    if origin:
        d["origin_url"] = origin
    return d


U = {
    "drupal_thn": "https://thehackernews.com/2026/11/drupal-fail2install-exploit-details.html",
    "drupal_bc": "https://www.bleepingcomputer.com/news/security/hackers-now-exploit-critical-drupal-rce-flaw-to-hijack-sites/",
    "geoserver": "https://thehackernews.com/2026/11/hackers-exploit-two-geoserver-flaws-as.html",
    "fragnesia": "https://www.bleepingcomputer.com/news/security/palo-alto-networks-warns-of-fragnesia-flaw-exploited-in-pan-os-attacks/",
    "infratrust": "https://www.bleepingcomputer.com/news/security/infratrust-warns-of-exploited-supply-chain-flaws-in-network-appliances/",
    "1password": "https://www.bleepingcomputer.com/news/security/1password-customer-data-stolen-after-employee-github-account-breach/",
    "github_sha": "https://thehackernews.com/2026/11/hackers-found-way-around-github-sha.html",
    "nuget": "https://thehackernews.com/2026/11/13-malicious-nuget-packages-turn-fake.html",
    "single_bit": "https://thehackernews.com/2026/11/google-researcher-shows-how-single-bit.html",
    "openai_tc": "https://techcrunch.com/2026/11/25/openai-says-heavy-chatgpt-users-may-hit-limits-sooner-as-it-merges-chat-and-work/",
    "benzinga": "https://www.benzinga.com/markets/ipos/26/11/63659606/openai-free-pop-over-anthropic-ipo-rout-luke-lango-jay-ritter-late-2027-ipo-recover",
    "gpt6": "https://openai.com/index/gpt-6-protein-design/",
}

ITEMS = [
    _it("The Hacker News", "Drupal Fail2Install Exploit Details and Patch Guidance", U["drupal_thn"]),
    _it("BleepingComputer", "Hackers Now Exploit Critical Drupal RCE Flaw to Hijack Sites", U["drupal_bc"]),
    _it("The Hacker News", "Hackers Exploit Two GeoServer Flaws as Zero-Days", U["geoserver"]),
    _it("BleepingComputer", "Palo Alto Networks Warns of Fragnesia Flaw Exploited in PAN-OS Attacks", U["fragnesia"]),
    _it("BleepingComputer", "Infratrust Warns of Exploited Supply Chain Flaws in Network Appliances", U["infratrust"]),
    _it("BleepingComputer", "1Password Customer Data Stolen After Employee GitHub Account Breach", U["1password"]),
    _it("The Hacker News", "Hackers Found Way Around GitHub SHA Pinning Protection", U["github_sha"]),
    _it("The Hacker News", "13 Malicious NuGet Packages Turn Fake Job Tasks Into Malware", U["nuget"]),
    _it("The Hacker News", "Google Researcher Shows How Single Bit Flip Breaks Isolation", U["single_bit"]),
    _it("TechCrunch AI", "OpenAI Says Heavy ChatGPT Users May Hit Limits Sooner as It Merges Chat and Work", U["openai_tc"]),
    _it("Anthropic GNews", "OpenAI Free Pop Over Anthropic IPO Rout, Luke Lango Sees Late 2027 IPO Recovery", U["benzinga"]),
    _it("OpenAI Blog", "GPT-6 Demonstrates Protein Design Capabilities in Lab Tests", U["gpt6"]),
    # df 보정용 채움 — hackers·github·openai를 흔한 토큰으로 만든다
    _it("The Hacker News", "Hackers Target GitHub Repositories in New Phishing Campaign",
        "https://thehackernews.com/2026/11/hackers-target-github-repositories.html"),
    _it("GitHub Blog", "GitHub Rolls Out New Security Features for Open Source",
        "https://github.blog/2026-11-25-security-features/"),
    _it("BleepingComputer", "Hackers Exploit Unpatched VPN Flaws, CISA Warns",
        "https://www.bleepingcomputer.com/news/security/hackers-exploit-unpatched-vpn-flaws/"),
    _it("OpenAI Blog", "OpenAI Announces New API Pricing for Developers",
        "https://openai.com/index/api-pricing-update/"),
    _it("GitHub Blog", "GitHub Copilot Gets New Agent Mode",
        "https://github.blog/2026-11-24-copilot-agent-mode/"),
    _it("Anthropic Blog", "Anthropic Releases Claude Update With Longer Context",
        "https://www.anthropic.com/news/claude-update"),
    _it("Reuters", "OpenAI Partners With Hospitals on AI Tools",
        "https://www.reuters.com/technology/openai-hospitals/"),
    _it("Microsoft Blog", "Microsoft Adds OpenAI Models to Azure",
        "https://blogs.microsoft.com/azure-openai-models/"),
]
BY_URL = {url_core(it["url"]): it for it in ITEMS}


def _src(url, handle):
    return {"handle": handle, "url": url, "kind": "news"}


def _analysis(aid, title, bullets, body, takeaway, sources):
    return {"id": aid, "title": title, "bullets": bullets, "body": body,
            "takeaway": takeaway, "sources": sources}


ISSUE = {
    "date": "2026-11-26",
    "title": "보안 결함 3건이 하루에 몰린 날",
    "heroline": "보안 결함 3건이 하루에 몰린 날",
    "dek": "", "tag": "security", "briefMin": 3, "readMin": 14,
    "briefing": [
        {"id": f"a{i}", "headline": f"헤드라인 {i}", "summary": f"요약 {i}"}
        for i in range(6)
    ],
    "keywords": ["보안"], "mainEvent": "Drupal 취약점",
    "keynums": [], "timeline": [], "intro": "", "method": "",
    "mood": {"shift": "s", "grow": "g", "caution": "c", "heat": "h"},
    "tips": [],
    "analysis": [
        _analysis(
            "a0", "1. Drupal 코어 RCE 취약점, 실제 공격과 11월 27일 패치 마감 동시 발생",
            ["Drupal 코어 원격 코드 실행 취약점이 무단 패치되지 않은 사이트를 장악하는 공격에 실제로 쓰이고 있습니다.",
             "미국 CISA가 이 결함을 알려진 악용 취약점 목록에 올렸습니다."],
            ["미국 사이버보안인프라보안국(CISA)이 Drupal 코어의 치명적 취약점을 알려진 악용 취약점(KEV) 목록에 추가했습니다. 이 결함은 'Fail2Install'이라는 이름으로 불립니다.",
             "Drupal 보안팀은 이 취약점을 이용한 사이트 장악 시도가 실제로 관측됐다고 확인했습니다."],
            "표준 구성을 벗어난 경로까지 영향이 열려 있다는 점이 위험을 키우는 대목입니다. Drupal 사이트 운영자는 11월 27일 이전에 코어 패치 적용부터 점검하면 됩니다.",
            [_src(U["drupal_thn"], "The Hacker News"),
             _src(U["drupal_bc"], "BleepingComputer"),
             _src(U["geoserver"], "The Hacker News")],
        ),
        _analysis(
            "a1", "2. 팔로알토, PHP2Shell·Fragnesia 연계 공격에 관리면 폐쇄 권고",
            ["공격자가 두 취약점의 익스플로잇을 연달아 묶어 팔로알토 장비를 노리고 있습니다.",
             "표적은 관리 인터페이스가 인터넷에 노출된 PAN-OS 기기입니다."],
            ["팔로알토 네트웍스가 PAN-OS 기기를 겨냥한 공격 경보를 냈습니다. PHP2Shell과 Fragnesia로 불리는 두 취약점의 익스플로잇을 연결해 쓰고 있다는 내용입니다.",
             "방화벽·VPN 같은 경계 장비는 최근 몇 년간 최우선 공격 표적이 되어 왔습니다."],
            "경계 장비의 관리면 노출이 실제 공격의 문이 된 사례입니다. 인프라 담당자는 PAN-OS 관리 인터페이스 노출 폐쇄를 우선순위에 반영해 두면 됩니다.",
            [_src(U["fragnesia"], "BleepingComputer"),
             _src(U["infratrust"], "BleepingComputer")],
        ),
        _analysis(
            "a2", "3. 1Password, 직원 GitHub 계정 해킹을 통한 고객 데이터 유출 공개",
            ["직원의 사내 GitHub 계정이 해킹돼 백엔드 서비스에 악성 코드가 배포됐습니다.",
             "이 경로로 고객 데이터가 유출됐다고 회사가 직접 공개했습니다."],
            ["비밀번호 관리 서비스 1Password가 데이터 유출 사고를 공개했습니다. 직원의 사내 GitHub 계정이 해킹당했고, 이 계정을 통해 회사 백엔드 서비스에 악성 코드가 배포됐습니다.",
             "이 침해에서 공격 경로는 외부 침투가 아니라 개발자 계정 탈취였습니다."],
            "보안 제품 회사의 개발자 계정이 뚫렸다는 점이 약점을 보여 줍니다. 1Password 이용 조직은 공지된 유출 항목을 확인하면 됩니다.",
            [_src(U["1password"], "BleepingComputer"),
             _src(U["github_sha"], "The Hacker News")],
        ),
        _analysis(
            "a3", "4. 가짜 입사 과제 위장 NuGet 악성 패키지 13개 발견",
            [".NET 개발자를 겨냥한 악성 NuGet 패키지 13개가 확인됐습니다.",
             "WinUI와 WPF 버튼 컨트롤로 위장해 멀웨어를 전달합니다."],
            ["보안 연구자가 윈도 .NET 개발자를 표적으로 하는 악성 NuGet 패키지 13개를 발견했습니다. Socket의 보안 연구자가 기술 보고서로 정리했습니다.",
             "감염 조건은 프로젝트 참조 후 빌드·실행이므로 단순 열람만으로는 성립하지 않습니다."],
            "채용 과제를 가장한 공급망 공격이 반복되는 대목입니다. 개발팀은 외부 저장소 참조를 막는 규칙에 반영해 두면 됩니다.",
            [_src(U["nuget"], "The Hacker News"),
             _src(U["single_bit"], "The Hacker News")],
        ),
        _analysis(
            "a4", "5. OpenAI, ChatGPT 챗·워크 통합과 단일 사용량 계량",
            ["OpenAI가 ChatGPT 챗과 워크를 하나로 통합했습니다.",
             "사용량 계량이 단일 기준으로 바뀝니다."],
            ["OpenAI가 ChatGPT의 챗과 워크 기능을 통합하고 사용량 계량을 단일 기준으로 바꿨습니다. 상위 요금제 무료 혜택이 사라지는 대신 하나의 사용량 기준으로 묶입니다.",
             "사용량이 많은 이용자는 상한에 먼저 도달할 수 있습니다."],
            "요금제 구조가 단순해지는 대신 헤비 유저의 상한 도달이 빨라지는 대목입니다. 팀 관리자는 사용량 기준 변경을 확인하면 됩니다.",
            [_src(U["openai_tc"], "TechCrunch AI"),
             _src(U["benzinga"], "Anthropic GNews")],
        ),
        _analysis(
            "a5", "6. GPT-6, 자체 단백질 설계 능력 입증",
            ["GPT-6가 단백질 설계 능력을 보였습니다.",
             "5개 표적에서 결합 증거가 확인됐습니다."],
            ["OpenAI가 GPT-6의 자체 단백질 설계 능력을 실험실 시험으로 확인했습니다. 추론과 코드 실행으로 단백질 구조·서열을 설계했습니다.",
             "다만 실험실 조건의 결과라 실제 환경 적용까지는 검증이 더 필요합니다."],
            "모델이 과학 실험 설계까지 들어간 대목이 중요합니다. 연구 조직은 재현 검증 결과를 확인하면 됩니다.",
            [_src(U["gpt6"], "OpenAI Blog")],
        ),
    ],
}

# --- 1. SRC-ORPHAN-001: 11-26 유형 A·B 5건이 잡히고 정상 출처는 통과 --------

orphans = src_orphan_findings(ISSUE, BY_URL)
orphan_pairs = {(f["analysis_index"], f["domain"]) for f in orphans}
ok("ORPHAN: 분석1 GeoServer (유형 A)", (0, "thehackernews.com") in orphan_pairs)
ok("ORPHAN: 분석2 Infratrust (유형 A)", (1, "bleepingcomputer.com") in orphan_pairs)
ok("ORPHAN: 분석3 GitHub SHA (유형 B — 회사명만 겹침)", (2, "thehackernews.com") in orphan_pairs)
ok("ORPHAN: 분석4 단일 비트 (유형 A)", (3, "thehackernews.com") in orphan_pairs)
ok("ORPHAN: 분석5 Benzinga IPO (유형 A)", (4, "benzinga.com") in orphan_pairs)
ok("ORPHAN: 분석6 정상 출처는 판정 없음", all(f["analysis_index"] != 5 for f in orphans))
ok("ORPHAN: 정상 출처 오탐 없음 (총 5건)", len(orphans) == 5)

# --- 2. SRC-TOPIC 대조: Benzinga는 토큰 겹침으로 통과 (ORPHAN이 필요한 이유) --

topics = src_topic_findings(ISSUE, BY_URL)
topic_pairs = {(f["analysis_index"], f["domain"]) for f in topics}
ok("SRC-TOPIC: GeoServer는 잡힘", (0, "thehackernews.com") in topic_pairs)
ok("SRC-TOPIC: Benzinga는 openai 겹침으로 통과 (한계 확인)",
   all(f["analysis_index"] != 4 for f in topics))

# --- 3. check() 경고 배선 ------------------------------------------------------

_errors, warnings = check_quality(ISSUE, set(BY_URL), None, "2026-11-26", BY_URL)
orphan_warns = [w for w in warnings if w.startswith("SRC-ORPHAN-001")]
ok("check(): SRC-ORPHAN-001 경고 5건", len(orphan_warns) == 5)
ok("check(): SRC-ORPHAN은 error가 아님 (warning 시작)",
   not any("SRC-ORPHAN" in e for e in _errors))

# --- 4. 0단계: collect_structured_errors에 SRC 판정 실림 ----------------------

structured = collect_structured_errors(ISSUE, BY_URL)
codes = [e["code"] for e in structured]
ok("sidecar: SRC-ORPHAN-001 5건", codes.count("SRC-ORPHAN-001") == 5)
ok("sidecar: SRC-TOPIC 실림 (GeoServer)", "SRC-TOPIC" in codes)
orphan_entry = next(e for e in structured if e["code"] == "SRC-ORPHAN-001"
                    and e["analysis_index"] == 4)
ok("sidecar: ORPHAN 항목에 analysis_id·domain 구조화",
   orphan_entry.get("analysis_id") == "a4"
   and orphan_entry.get("domain") == "benzinga.com")

# --- 5. 0단계: SRC-REL-001/101 findings + 게이트 문자열 회귀 ------------------

REL_ISSUE = {"analysis": [
    _analysis("r0", "OpenAI, 새 추론 모델 공개",
              ["불릿"], ["본문"], "시사점입니다.",
              [_src("https://www.anthropic.com/news/claude-update", "Anthropic Blog")]),
    _analysis("r1", "GitHub, 새 보안 기능 공개",
              ["불릿"], ["본문"], "시사점입니다.",
              [_src("https://example.org/some-post", "GitHub")]),
]}
rel_findings = src_rel_findings(REL_ISSUE, None)
rel_codes = {(f["code"], f["analysis_index"]) for f in rel_findings}
ok("SRC-REL-001 findings", ("SRC-REL-001", 0) in rel_codes)
ok("SRC-REL-101 findings", ("SRC-REL-101", 1) in rel_codes)
holds, _w = check_source_relevance(REL_ISSUE, None)
ok("게이트 문자열 회귀: SRC-REL-001 hold 유지",
   any(h.startswith("SRC-REL-001 analysis[0]") for h in holds))
ok("게이트 문자열 회귀: SRC-REL-101 hold 유지",
   any(h.startswith("SRC-REL-101 analysis[1]") for h in holds))
rel_structured = collect_structured_errors(REL_ISSUE, None)
rel_scodes = {e["code"] for e in rel_structured}
ok("sidecar: SRC-REL-001 실림", "SRC-REL-001" in rel_scodes)
ok("sidecar: SRC-REL-101 실림", "SRC-REL-101" in rel_scodes)

# --- 6. render_feedback: 처방 렌더링 + 앵커 방지 ------------------------------

with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8") as _f:
    json.dump({"errors": structured + rel_structured}, _f)
    _sidecar = _f.name
fb = render_feedback(_sidecar)
ok("피드백: 고립 출처 처방 포함", "고립 출처" in fb and "benzinga.com" in fb)
ok("피드백: SRC-TOPIC 처방 포함", "무관해 보입니다" in fb)
ok("피드백: SRC-REL-001 처방 포함", "무관한" in fb and "anthropic.com" in fb)
ok("피드백: SRC-REL-101 처방 포함", "example.org" in fb)
ok("피드백 앵커 방지: 무관 출처 제목은 인용 안 함",
   "GeoServer" not in fb and "Infratrust" not in fb)

# --- 7. 프롬프트 규칙 명시 -----------------------------------------------------

ok("프롬프트: 무관 출처 교체 규칙 명시",
   "무관 출처로 지적된 출처는 다음 시도에서 같은 이야기의 아이템으로 교체" in PROMPT)

print(f"P32 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
