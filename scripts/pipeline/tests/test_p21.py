#!/usr/bin/env python3
"""P21 회귀 테스트: freshness-check 모니터 모드 (5차 평가 P2).

배경: freshness-check가 validate.py를 --collected 없이 호출하는데, collected
스냅샷은 gitignore라 체크아웃에 존재할 수 없다. 발행 시점의 numbers 슬롯
제외 판정(입력 수치 후보 대조)을 사후 재현할 수 없어, 정상 발행본이 depth
집계 에러로 매일 오경보를 냈다. --monitor 모드는 numbers 슬롯만 판정
보류하고 나머지 검사는 그대로 수행한다. 발행 게이트(기본 모드)의
fail-closed 동작은 변하지 않아야 한다.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import check_depth

PASS = 0
FAIL = 0


def ok(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _make_analysis(num_count: int, short_takeaway: bool = False):
    """test_p0와 같은 픽스처: num_count개의 수치를 가진 analysis."""
    nums = " ".join(f"{i+1}배" for i in range(num_count))
    return {
        "id": "a1", "title": "테스트 기사",
        "bullets": ["불릿 하나", "불릿 둘", "불릿 셋"],
        "body": [
            f"첫 번째 문단입니다. {nums} 수치가 있습니다. " * 3,
            "두 번째 문단입니다. 배경과 맥락을 설명합니다. 하지만 한계도 있습니다. " * 2,
        ],
        "takeaway": "짧음" if short_takeaway else "이 변화는 시장에 중요한 영향을 줍니다. 담당자는 이번 주 안에 검토하면 됩니다.",
        "tags": ["AI"], "sources": [{"url": "https://example.com/x"}],
    }


# 1. 집계: 3개 기사 전부 numbers만 미충족 → 기본 모드는 전체 생략 에러,
#    모니터 모드는 판정 보류로 통과 + 보류 경고 3개.
issue_all_numbers = {
    "date": "2026-11-16", "briefing": [],
    "analysis": [_make_analysis(0), _make_analysis(0), _make_analysis(0)],
}
derr_gate, _ = check_depth(issue_all_numbers)
ok("기본 모드: numbers 3개 생략은 전체 생략 에러 (fail-closed 유지)",
   any("전체 슬롯 생략" in e for e in derr_gate))
derr_mon, dwarn_mon = check_depth(issue_all_numbers, monitor=True)
ok("모니터 모드: numbers 판정 보류로 전체 생략 에러 없음",
   not any("전체 슬롯 생략" in e for e in derr_mon))
ok("모니터 모드: 판정 보류 경고 3개",
   sum(1 for w in dwarn_mon if "판정 보류" in w) == 3)

# 2. 기사별: numbers+why 2개 미충족 → 기본 모드는 "슬롯 2개 미충족" 에러,
#    모니터 모드는 why 1개 생략(경고)으로 축소되어 에러 없음.
issue_two_missing = {
    "date": "2026-11-16", "briefing": [],
    "analysis": [_make_analysis(0, short_takeaway=True)],
}
derr2_gate, _ = check_depth(issue_two_missing)
ok("기본 모드: 슬롯 2개 미충족 에러", any("슬롯 2개 미충족" in e for e in derr2_gate))
derr2_mon, dwarn2_mon = check_depth(issue_two_missing, monitor=True)
ok("모니터 모드: 슬롯 2개 미충족 에러 없음", not any("미충족" in e for e in derr2_mon))
ok("모니터 모드: why 생략 경고는 남음", any("슬롯 1개 생략 (why)" in w for w in dwarn2_mon))

# 3. 모니터 모드가 다른 슬롯까지 봐주지 않는다: what+context+why 동시 미충족은
#    numbers를 보류해도 여전히 에러여야 한다.
bad = _make_analysis(0, short_takeaway=True)
bad["body"] = ["짧다"]
issue_bad = {"date": "2026-11-16", "briefing": [], "analysis": [bad]}
derr3_mon, _ = check_depth(issue_bad, monitor=True)
ok("모니터 모드: numbers 외 다중 미충족은 여전히 에러", any("미충족" in e for e in derr3_mon))

# 4. collected가 실제로 있으면 모니터 모드라도 기존 제외 판정이 우선한다:
#    입력 후보 1개 → "numbers 슬롯 제외" 경고가 나오고 "판정 보류"는 없어야 한다.
from validate import url_core
cmap = {url_core("https://a.com/2"): {"url": "https://a.com/2", "summary": "매출이 2배로 뛰었다"}}
a_src = _make_analysis(0)
a_src["sources"] = [{"url": "https://a.com/2"}]
issue_excused = {"date": "2026-11-16", "briefing": [], "analysis": [a_src]}
_, dwarn4 = check_depth(issue_excused, cmap, monitor=True)
ok("collected 우선: 제외 경고 사용", any("numbers 슬롯 제외" in w for w in dwarn4))
ok("collected 우선: 판정 보류 경고 없음", not any("판정 보류" in w for w in dwarn4))

# 5. CLI 통합: 실제 발행본(2026-11-16)이 --monitor에서 통과하고 기본 모드에서 실패.
repo_root = Path(__file__).resolve().parents[3]
validate_py = Path(__file__).resolve().parents[1] / "validate.py"
issue_file = repo_root / "content" / "issues" / "2026-11-16.json"
if issue_file.exists():
    r_mon = subprocess.run(
        [sys.executable, str(validate_py), "--monitor", "--date", "2026-11-16", str(issue_file)],
        capture_output=True, text=True)
    ok("CLI --monitor: 2026-11-16호 통과 (exit 0)", r_mon.returncode == 0)
    r_gate = subprocess.run(
        [sys.executable, str(validate_py), "--date", "2026-11-16", str(issue_file)],
        capture_output=True, text=True)
    ok("CLI 기본 모드: 2026-11-16호 실패 유지 (exit 1)", r_gate.returncode == 1)
else:
    print("  SKIP: content/issues/2026-11-16.json 없음 — CLI 통합 테스트 생략")

print(f"P21 tests: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
