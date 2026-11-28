#!/usr/bin/env python3
"""P41 회귀 테스트: 영어 점수 소수의 NUMBERS-UNGROUNDED 오탐 차단.

배경 (실측, 2026-11-26·27호): Drupal Fail2Install 이야기의 출처
(The Hacker News) 요약에 "(CVSS score: 9.8)"이 실제로 있는데, 입력 스캔용
NUM_RE는 단위가 붙은 수치만 잡아 단위 없는 소수 9.8이 허용 집합에 못
들어갔고, LLM의 정확한 변환 "9.8점"이 NUMBERS-UNGROUNDED로 사흘 연속
(11/26 run 119, 11/27 run 121·122) attempt를 소모했다.
→ 입력 스캔에서만 점수 문맥(cvss·score·rating·grade)의 소수와 "N/10"
평점 표기를 canon으로 연결한다 (P18b·P20과 같은 입력 전용 보강 방식).
버전 번호 같은 무관한 소수는 문맥이 없어 여전히 허용되지 않는다.
픽스처 문장은 실측 아티팩트 요약을 축약한 것이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    return {"source": source, "kind": "news", "title": title, "url": url,
            "summary": summary, "published": "2026-11-26T09:00:00+09:00"}


def _by_url(items):
    out = {}
    for it in items:
        out.setdefault(url_core(it["url"]), it)
    return out


def _analysis(aid, url, bullets, body):
    return {"id": aid, "title": "t", "bullets": bullets, "body": body,
            "takeaway": "판단입니다. 다음 행동을 하면 됩니다.", "extra": "",
            "sources": [{"url": url}]}


THN_URL = "https://thehackernews.com/2026/11/drupal-fail2install-exploit-details.html"
THN = _it(
    "The Hacker News",
    "Drupal Fail2Install Exploit Details Emerge as Critical RCE Flaw Faces Active Exploitation",
    THN_URL,
    "The U.S. Cybersecurity and Infrastructure Security Agency (CISA) on Tuesday "
    "added a critical flaw impacting Drupal to its Known Exploited Vulnerabilities "
    "(KEV) catalog, requiring federal agencies to apply the fixes by November 27, "
    "2026. The vulnerability, tracked as CVE-2026-132165 aka Fail2Install "
    "(CVSS score: 9.8), is a case of remote code execution (RCE) impacting "
    "Drupal core.",
)

# ---------- 1. 실측 케이스: CVSS 점수 소수 → "9.8점" 근거 인정 ----------
a = _analysis(
    "drupal-fail2install", THN_URL,
    ["CVE-2026-132165, CVSS 9.8점 원격 코드 실행 결함"],
    ["결함은 CVE-2026-132165, 별칭 Fail2Install로, 원격 코드 실행(RCE) "
     "유형이며 CVSS 점수는 9.8점입니다."],
)
d = _numbers_grounded_detail(a, _by_url([THN]))
ok("CVSS score 9.8 → '9.8점' grounded", d["grounded"] and not d["bad"])
ok("허용 목록에 점수 표면이 실린다",
   any("9.8" in x for x in d["allowed_raw"]))

# ---------- 2. 음성 대조: 점수 문맥 없는 소수(버전)는 여전히 차단 ----------
VER_URL = "https://example.com/cms-release"
ver = _it("Example", "CMS 11.2 released with installer fixes", VER_URL,
          "The team released version 11.2 of the CMS on Tuesday, fixing the "
          "installer states left over from the previous release.")
a2 = _analysis("cms-release", VER_URL,
               ["보안 점수 11.2점 수준의 결함"],
               ["이 결함의 심각도는 11.2점입니다."])
d2 = _numbers_grounded_detail(a2, _by_url([ver]))
ok("버전 소수 11.2는 점수 근거가 되지 않는다",
   not d2["grounded"] and any(b["raw"] == "11.2점" for b in d2["bad"]))

# ---------- 3. "N/10" 평점 표기와 rating 문맥 ----------
RT_URL = "https://example.com/tool-review"
rt = _it("Example", "Tool review roundup", RT_URL,
         "Reviewers rated the tool 8.4/10 overall, praising its speed.")
a3 = _analysis("tool-review", RT_URL,
               ["평론가 평점 8.4점"],
               ["평론가 평점은 8.4점입니다."])
d3 = _numbers_grounded_detail(a3, _by_url([rt]))
ok("rated 8.4/10 → '8.4점' grounded", d3["grounded"] and not d3["bad"])

# ---------- 4. 점수가 있어도 다른 값의 점수는 차단 ----------
a4 = _analysis("drupal-fail2install", THN_URL,
               ["CVSS 3.2점 수준"],
               ["심각도는 3.2점입니다."])
d4 = _numbers_grounded_detail(a4, _by_url([THN]))
ok("근거 없는 다른 점수 3.2점은 여전히 차단",
   not d4["grounded"] and any(b["raw"] == "3.2점" for b in d4["bad"]))

print(f"test_p41: PASS {PASS} / FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
