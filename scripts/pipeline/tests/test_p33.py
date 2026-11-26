#!/usr/bin/env python3
"""P33 회귀 테스트: 말투 교정 게이트 (TERM-001 · TRANS-001 · HEAD-001).

기준: '초등학생 이해 가능'을 정식 발행 기준으로 채택. 단 전부
warning + 재시도 피드백으로 시작한다 (error 아님).

픽스처는 2026-11-26호 실제 문장이다:
- 정상: "악성 코드는 고객 데이터를 빼내는 데 쓰였다고 회사가 밝혔습니다"
  (분석 3 본문 — 어떤 게이트에도 걸리지 않아야 한다)
- 용어 무풀이: "표적은 관리 인터페이스가 인터넷에 노출된 PAN-OS
  기기입니다" (분석 2 불릿 — TERM-001)
- 번역투: "인류가 AI에 자유 의향을 내주는 방향을 원하지 않는다고
  밝혔습니다" (분석 7 — TRANS-001)
- 단정 과잉: 분석 6 제목 '단백질 설계 입증' vs 본문의 '확인되지
  않습니다·미확정' (HEAD-001)
풀이 표기(EN↔KO 표면 쌍)가 있으면 통과하는지도 쌍으로 고정한다.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import PROMPT, render_feedback
from validate import (
    check_quality,
    collect_structured_errors,
    head_assert_findings,
    term_gloss_findings,
    trans_lit_findings,
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


def _analysis(aid, title, bullets, body, takeaway=""):
    return {"id": aid, "title": title, "bullets": bullets, "body": body,
            "takeaway": takeaway, "sources": []}


def _issue(analyses, briefing=None, title="", heroline=""):
    return {
        "date": "2026-11-26", "title": title, "heroline": heroline,
        "dek": "", "tag": "x", "briefMin": 3, "readMin": 14,
        "briefing": briefing or [], "keywords": [], "mainEvent": "",
        "keynums": [], "timeline": [], "intro": "", "method": "",
        "mood": {"shift": "", "grow": "", "caution": "", "heat": ""},
        "tips": [], "analysis": analyses,
    }


# --- 1. 정상 문장: 어떤 말투 게이트에도 걸리지 않는다 -------------------------

iss_clean = _issue([_analysis(
    "a3", "3. 1Password, 직원 GitHub 계정 해킹 공개",
    ["직원의 사내 GitHub 계정이 해킹돼 백엔드 서비스에 악성 코드가 배포됐습니다."],
    ["악성 코드는 고객 데이터를 빼내는 데 쓰였다고 회사가 밝혔습니다."],
)])
ok("정상 문장: TERM 없음", term_gloss_findings(iss_clean) == [])
ok("정상 문장: TRANS 없음", trans_lit_findings(iss_clean) == [])
ok("정상 문장: HEAD 없음", head_assert_findings(iss_clean) == [])

# --- 2. TERM-001: PAN-OS 무풀이 (실측 문장) -----------------------------------

iss_panos = _issue([_analysis(
    "a2", "2. 팔로알토, 연계 공격에 관리면 폐쇄 권고",
    ["표적은 관리 인터페이스가 인터넷에 노출된 PAN-OS 기기입니다."],
    ["팔로알토 네트웍스가 공격 경보를 냈습니다."],
)])
tf = term_gloss_findings(iss_panos)
ok("TERM: PAN-OS 무풀이 지적", len(tf) == 1 and tf[0]["term"] == "PAN-OS")
ok("TERM: 위치는 analysis[0]", tf and tf[0]["loc"] == "analysis[0]")

# 풀이를 붙이면 통과 (제품명 뒤 괄호)
iss_panos_gloss = _issue([_analysis(
    "a2", "2. 팔로알토, 연계 공격에 관리면 폐쇄 권고",
    ["표적은 관리 인터페이스가 인터넷에 노출된 PAN-OS(팔로알토 방화벽 운영체제) 기기입니다."],
    ["이후 문장에서는 PAN-OS만 써도 됩니다."],
)])
ok("TERM: 괄호 풀이가 있으면 통과 + 이후 무풀이 허용",
   term_gloss_findings(iss_panos_gloss) == [])

# --- 3. TERM-001 EN↔KO 표면 쌍: 약어는 한국어 풀이 + 괄호로 통과 --------------

iss_rce_gloss = _issue([_analysis(
    "a1", "1. Drupal 코어 RCE 취약점, 실제 공격 발생",
    ["원격 코드 실행(RCE) 취약점이 실제로 쓰이고 있습니다."],
    ["이 결함은 패치하지 않은 사이트를 장악하는 데 쓰입니다."],
)])
ok("TERM 쌍: '원격 코드 실행(RCE)'면 제목의 RCE도 통과",
   term_gloss_findings(iss_rce_gloss) == [])

iss_kev_gloss = _issue([_analysis(
    "a1", "1. Drupal 코어 취약점, KEV 등록",
    ["알려진 악용 취약점(KEV) 목록에 추가됐습니다."],
    ["KEV 등록은 연방기관 의무와 함께 대응 신호로 읽힙니다."],
)])
ok("TERM 쌍: '알려진 악용 취약점(KEV)'면 이후 무풀이 허용",
   term_gloss_findings(iss_kev_gloss) == [])

# 풀이 없는 약어는 지적 (CMS — 11-26호 분석 1 실측)
iss_cms = _issue([_analysis(
    "a1", "1. Drupal 코어 취약점",
    ["Drupal은 공공기관과 언론에 널리 쓰입니다."],
    ["Drupal은 널리 쓰이는 CMS라 영향 반경이 큽니다."],
)])
tf = term_gloss_findings(iss_cms)
ok("TERM: CMS 무풀이 지적", len(tf) == 1 and tf[0]["term"] == "CMS")

# 익스플로잇 무풀이 (11-26호 실측)
iss_exploit = _issue([_analysis(
    "a1", "1. Drupal 코어 취약점",
    ["취약점이 실제로 쓰이고 있습니다."],
    ["다만 이번 결함의 익스플로잇 상세가 최근 공개된 만큼 조치하는 것이 관건입니다."],
)])
tf = term_gloss_findings(iss_exploit)
ok("TERM: 익스플로잇 무풀이 지적",
   len(tf) == 1 and tf[0]["term"] == "익스플로잇")

# --- 4. TRANS-001: 번역투 (실측 문장) ------------------------------------------

iss_trans = _issue([_analysis(
    "a7", "7. Anthropic CEO, 논란 직접 부인",
    ["인류가 AI에 자유 의향을 내주는 방향을 원하지 않는다고 밝혔습니다."],
    ["Anthropic 최고경영자가 자유 의향 논란에 직접 반응했습니다."],
)])
xf = trans_lit_findings(iss_trans)
ok("TRANS: '자유 의향' 지적", any(f["phrase"] == "자유 의향" for f in xf))
ok("TRANS: 교정 제안은 '자유 의지'",
   any(f["suggestion"] == "자유 의지" for f in xf))

iss_double_passive = _issue([_analysis(
    "a1", "1. 새 모델 공개",
    ["결과가 화면에 보여집니다."],
    ["본문입니다."],
)])
ok("TRANS: 이중 피동 '보여지' 지적",
   any(f["phrase"] == "보여지" for f in trans_lit_findings(iss_double_passive)))

# --- 5. HEAD-001: 제목 단정 vs 본문 조건 (실측 쌍) ------------------------------

iss_head = _issue([_analysis(
    "a6", "6. GPT-6 모델, 추론·코드 실행만으로 단백질 설계 입증",
    ["실험실 시험에서 5개 표적에서 결합 증거가 확인됐습니다."],
    ["결합의 세기에 대한 세부 지표는 이번 요약에서 확인되지 않습니다. "
     "상대적 성능은 미확정으로 두는 것이 정확합니다."],
    "범용 모델의 고유 능력으로 단백질 설계가 입증됐다는 점이 읽히는 의미가 큽니다.",
)])
hf = head_assert_findings(iss_head)
ok("HEAD: '입증' 제목 + 조건 본문 → 지적",
   len(hf) == 1 and hf[0]["marker"] == "입증")

# 본문이 단정을 뒷받침하면(조건 표지 없음) 경고하지 않는다
iss_head_ok = _issue([_analysis(
    "a6", "6. GPT-6 모델, 단백질 설계 입증",
    ["실험실 시험에서 5개 표적 전부 결합이 확인됐습니다."],
    ["회사가 공식 블로그로 결과를 발표했고, 재현 코드도 함께 공개했습니다."],
)])
ok("HEAD: 조건 표지 없는 본문이면 경고 없음", head_assert_findings(iss_head_ok) == [])

# 제목에 단정 표지가 없으면 본문에 조건이 있어도 경고하지 않는다
iss_head_plain = _issue([_analysis(
    "a6", "6. GPT-6 모델, 단백질 설계 능력 확인",
    ["실험실 시험에서 결합 증거가 확인됐습니다."],
    ["세부 지표는 확인되지 않습니다."],
)])
ok("HEAD: 단정 없는 제목이면 경고 없음", head_assert_findings(iss_head_plain) == [])

# --- 6. 배선: check_quality warning + sidecar + render_feedback ----------------

iss_all = _issue(
    [_analysis(
        "a2", "2. 팔로알토, 연계 공격 권고",
        ["표적은 관리 인터페이스가 인터넷에 노출된 PAN-OS 기기입니다."],
        ["팔로알토 네트웍스가 경보를 냈습니다."],
    ), _analysis(
        "a7", "7. Anthropic CEO, 논란 부인",
        ["인류가 AI에 자유 의향을 내주는 방향을 원하지 않는다고 밝혔습니다."],
        ["해명이 주목받는 배경은 회사의 공적 위상입니다."],
    ), _analysis(
        "a6", "6. GPT-6 모델, 단백질 설계 입증",
        ["실험실 시험에서 결합 증거가 확인됐습니다."],
        ["세부 지표는 확인되지 않습니다."],
    )],
)
_errors, warnings = check_quality(iss_all, set(), None, "2026-11-26", None)
ok("check_quality: TERM-001 warning", any(w.startswith("TERM-001") for w in warnings))
ok("check_quality: TRANS-001 warning", any(w.startswith("TRANS-001") for w in warnings))
ok("check_quality: HEAD-001 warning", any(w.startswith("HEAD-001") for w in warnings))
ok("check_quality: 말투 게이트는 error가 아님",
   not any(e.startswith(("TERM-001", "TRANS-001", "HEAD-001")) for e in _errors))

structured = collect_structured_errors(iss_all, None)
codes = [e["code"] for e in structured]
ok("sidecar: TERM-001 실림", "TERM-001" in codes)
ok("sidecar: TRANS-001 실림", "TRANS-001" in codes)
ok("sidecar: HEAD-001 실림", "HEAD-001" in codes)

with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8") as _f:
    json.dump({"errors": structured}, _f)
    _sidecar = _f.name
fb = render_feedback(_sidecar)
ok("피드백: TERM 처방 (괄호 풀이)", "PAN-OS" in fb and "괄호" in fb)
ok("피드백: TRANS 처방 (자유 의지)", "자유 의향" in fb and "자유 의지" in fb)
ok("피드백: HEAD 처방 (단정 수준)", "입증" in fb and "단정 수준" in fb)

# --- 7. 프롬프트 규칙 3종 -------------------------------------------------------

ok("프롬프트: 용어 풀이 규칙", "처음 등장할 때 쉬운 풀이" in PROMPT)
ok("프롬프트: 번역투 금지 규칙", "자유 의향" in PROMPT and "자유 의지" in PROMPT)
ok("프롬프트: 제목 단정 규칙", "단정 수준은 본문의 근거 수준" in PROMPT)

print(f"P33 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
