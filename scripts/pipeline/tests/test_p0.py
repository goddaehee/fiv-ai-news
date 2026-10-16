#!/usr/bin/env python3
"""P0 회귀 테스트: validate 8종 검사 + thicken_take/body 템플릿 제거."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate import check_p0, _normalize_sim, _overlap, _jaccard, check_depth, _input_number_count, url_core
from validate import check_source_quota, extract_domain, check_takeaway_template, _takeaway_skeleton
from draft import thicken_take, thicken_body, number_mentions
from select_items import bucket_domain, select_buckets, score_bucket, MIN_MAIN, MAX_MAIN

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def base_issue(**kw):
    issue = {
        "date": "2026-10-14",
        "mainEvent": "AI 실행력 보고서",
        "briefing": [
            {"id": "a1", "headline": "A가 B를 했다", "summary": "A가 B를 하면서 시장이 바뀌고 있다"},
        ],
        "analysis": [
            {
                "id": "a1",
                "title": "A가 B를 했다",
                "bullets": ["불릿1", "불릿2"],
                "body": ["첫 번째 문단입니다. 내용이 충분합니다.", "두 번째 문단입니다. 여기도 충분합니다."],
                "takeaway": "A의 B는 시장에 영향을 줍니다. 담당자는 이번 주 안에 검토하면 됩니다.",
                "tags": ["AI", "시장"],
                "sources": [],
            }
        ],
        "tips": [{"title": "팁 제목", "body": "팁 본문 내용입니다. 다릅니다.", "via": "공식 블로그"}],
    }
    issue.update(kw)
    return issue


# --- TPL-001 ---
ok("TPL-001 탐지", any("TPL-001" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0],
        "takeaway": "A은 오늘 확인할 변경입니다. 숫자·적용 범위·분모는 출처 문서에서 다시 보고."}]), None)[0]))
ok("TPL-001 정상 통과", not check_p0(base_issue(), None)[0])

# --- ID-001 ---
ok("ID-001 탐지", any("ID-001" in e for e in check_p0(
    base_issue(mainEvent="a1"), None)[0]))
ok("ID-001 정상 통과", not any("ID-001" in e for e in check_p0(base_issue(), None)[0]))

# --- DUP-001 ---
ok("DUP-001 탐지", any("DUP-001" in e for e in check_p0(
    base_issue(briefing=[{"id": "a1", "headline": "엔비디아가 새로운 AI 칩을 발표했다", "summary": "엔비디아가 새로운 AI 칩을 발표했다"}]), None)[0]))
ok("DUP-001 정상 통과", not any("DUP-001" in e for e in check_p0(base_issue(), None)[0]))

# --- ID-002 ---
ok("ID-002 탐지", any("ID-002" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "tags": ["a1"]}]), None)[0]))
ok("ID-002 빈태그 탐지", any("ID-002" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "tags": [" "]}]), None)[0]))

# --- DUP-002 ---
ok("DUP-002 탐지", any("DUP-002" in e for e in check_p0(
    base_issue(tips=[{"title": "초안 숫자는 공식 페이지에서 다시 봅니다", "body": "초안 숫자는 공식 페이지에서 다시 봅니다", "via": "블로그"}]), None)[0]))

# --- VIA-001 ---
ok("VIA-001 탐지", any("VIA-001" in e for e in check_p0(
    base_issue(tips=[{"title": "t", "body": "b", "via": "파이프라인"}]), None)[0]))
ok("VIA-001 빈값 탐지", any("VIA-001" in e for e in check_p0(
    base_issue(tips=[{"title": "t", "body": "b", "via": ""}]), None)[0]))

# --- thicken_take: 삭제 금지 (P0-1). 길이·어미 판정은 validator의 몫 ---
ok("thicken_take 템플릿 없음", "오늘 확인할 변경입니다" not in thicken_take("", ["불릿"], "제목"))
ok("thicken_take 미달도 삭제 안 함", thicken_take("짧음", ["불릿"], "제목") == "짧음")
good_take = "엔비디아의 새 AI 칩 발표는 데이터센터 시장에 직접 영향을 줍니다. 인프라 담당자는 이번 분기 안에 도입 타당성을 검토하면 됩니다. 추가로 가격 정책도 함께 확인합니다."
ok("thicken_take 정상 유지", thicken_take(good_take, ["불릿"], "제목") == good_take)
# 60~69자 takeaway가 코드에 의해 지워지면 안 됨 (이전 버그: 70자 미만 → "")
sixty = "신형 칩은 데이터센터 비용 구조를 바꾸는 데 중요하다. 인프라 팀은 이번 분기 안에 도입 타당성을 검토하면 됩니다."
ok("thicken_take 60자대 유지", 60 <= len(sixty) < 70 and thicken_take(sixty, ["불릿"], "제목") == sixty)

# --- number_mentions: 검증기 numbers 정규식과 동일한 후보 추출 ---
ok("number_mentions 기본", number_mentions("응답은 2배 빨라지고 가격은 30% 내렸다") == ["2배", "30%"])
# P1 (Codex): $2B, 2 million은 AI 뉴스에서 인정. 두 배(한글 서수), 2024년(연도)은 제외.
ok("number_mentions 불인정 제외", number_mentions("두 배 빨라졌다. 2024년에 출시.") == [])
ok("number_mentions 영어 단위 인정", number_mentions("$2B 투자, 2 million 파라미터") == ["$2B", "2 million"])
ok("number_mentions 중복 제거", number_mentions("30% 상승, 다시 30% 상승") == ["30%"])
ok("number_mentions 빈 입력", number_mentions("") == [])
# P1 (Codex) 엣지 케이스
ok("number_mentions 70B 추출", number_mentions("70B 파라미터 모델이 2배 빨라졌다") == ["70B", "2배"])
ok("number_mentions $300B 조사 뒤", number_mentions("가격이 $200에서 $300B으로 올랐다") == ["$200", "$300B"])
ok("number_mentions 10x 추출", number_mentions("2 million 파라미터, 10x 속도") == ["2 million", "10x"])
ok("number_mentions 모델명 제외", number_mentions("GPT-5와 Claude 3.5 비교") == [])
ok("number_mentions 연도 제외", number_mentions("2024년 발표") == [])

# --- thicken_body: 패딩 없음 ---
ok("thicken_body 패딩 없음", "조건과 분모는" not in " ".join(thicken_body(["짧은 본문"], ["불릿1"])))

# --- EMPTY-001/002 ---
ok("EMPTY-001 탐지", any("EMPTY-001" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "takeaway": ""}]), None)[0]))
ok("EMPTY-002 탐지", any("EMPTY-002" in e for e in check_p0(
    base_issue(analysis=[{**base_issue()["analysis"][0], "body": []}]), None)[0]))

# --- 오탐 방지: 정상 콘텐츠 ---
clean = {
    "mainEvent": "AI 에이전트 경쟁 심화",
    "briefing": [
        {"id": "b1", "headline": "엔비디아가 새로운 AI 칩을 발표했다",
         "summary": "데이터센터용 차세대 칩 공개. 전력 효율이 2배 개선됐다."},
    ],
    "analysis": [{
        "title": "엔비디아 신형 칩 분석",
        "body": ["첫 번째 문단입니다. 전력 효율 개선이 핵심입니다.", "두 번째 문단입니다. 가격은 아직 공개되지 않았습니다."],
        "takeaway": "신형 칩은 데이터센터 비용을 낮춥니다. 인프라 팀은 이번 분기 도입을 검토하면 됩니다.",
        "tags": ["AI", "반도체", "엔비디아"],
    }],
    "tips": [{"title": "GPU 비용 절감 팁", "body": "스팟 인스턴스를 활용하면 비용을 70% 줄일 수 있습니다.", "via": "AWS 블로그"}],
}
ce, cw = check_p0(clean, None)
ok("정상 콘텐츠 오탐 없음", not ce)

# --- P1: depth 임계값 산술 수정 (Claude C-3) ---
# 허용 생략 = max(2, ceil(전체슬롯 × 0.10)). 15슬롯이면 2개 허용.
def _allowed_missing(total_slots: int) -> int:
    return max(2, -(-total_slots // 10))

ok("depth 임계값 15슬롯→2개", _allowed_missing(15) == 2)
ok("depth 임계값 25슬롯→3개", _allowed_missing(25) == 3)
ok("depth 임계값 50슬롯→5개", _allowed_missing(50) == 5)

# 실제 check_depth로 2개 생략이 통과하는지 검증
def _make_analysis(num_count: int, short_takeaway: bool = False):
    """num_count개의 수치를 가진 analysis 생성."""
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

# 3개 기사 중 2개가 numbers 슬롯 비움 → 2/15 = 13.3% → 허용 2개라 통과
issue_2missing = {
    "date": "2026-10-15", "briefing": [],
    "analysis": [_make_analysis(2), _make_analysis(0), _make_analysis(0)],
}
derr, _ = check_depth(issue_2missing)
ok("depth 2개 생략 통과", not any("전체 슬롯 생략" in e for e in derr))

# 3개 생략 → 허용 초과로 실패
issue_3missing = {
    "date": "2026-10-15", "briefing": [],
    "analysis": [_make_analysis(2), _make_analysis(0), _make_analysis(0, short_takeaway=True)],
}
derr3, _ = check_depth(issue_3missing)
ok("depth 3개 생략 실패", any("전체 슬롯 생략" in e for e in derr3))

# --- P2: 조건부 excused (패널 만장일치) ---
# 입력 summary에 수치 후보가 2개 미만이면 numbers 슬롯을 생략률 계산에서 제외.
# 조인 불가(--collected 없음·URL 불일치)면 None → fail-closed(제외 안 함).

def _collected_map(*items):
    """(url, summary) 튜플들을 collected_by_url 맵으로."""
    m = {}
    for url, summary in items:
        m[url_core(url)] = {"url": url, "summary": summary}
    return m

def _analysis_with_source(url):
    a = _make_analysis(0)  # numbers 슬롯 비어 있음
    a["sources"] = [{"url": url}]
    return a

# 1. _input_number_count: 후보 수 반환
cmap = _collected_map(
    ("https://a.com/1", "매출이 2배로 뛰었고 30% 성장했다"),  # 2개
    ("https://a.com/2", "매출이 2배로 뛰었다"),               # 1개
    ("https://a.com/3", "숫자 없는 발표문이다"),               # 0개
)
ok("input_number 2개", _input_number_count(_analysis_with_source("https://a.com/1"), cmap) == 2)
ok("input_number 1개", _input_number_count(_analysis_with_source("https://a.com/2"), cmap) == 1)
ok("input_number 0개", _input_number_count(_analysis_with_source("https://a.com/3"), cmap) == 0)
ok("input_number URL 불일치→None", _input_number_count(_analysis_with_source("https://b.com/x"), cmap) is None)
ok("input_number map None→None", _input_number_count(_analysis_with_source("https://a.com/1"), None) is None)

# 2. check_depth excused: numbers 미충족 + 입력 후보 1개 → error 없음 + warning 1개
issue_excused = {
    "date": "2026-10-15", "briefing": [],
    "analysis": [_analysis_with_source("https://a.com/2")],  # 후보 1개 < 2
}
derr_e, dwarn_e = check_depth(issue_excused, cmap)
ok("excused: numbers 제외로 error 없음", not any("numbers" in e and "미충족" in e for e in derr_e))
ok("excused: 전체 생략 error 없음", not any("전체 슬롯 생략" in e for e in derr_e))
ok("excused: warning 기록됨", any("numbers 슬롯 제외" in w and "1개 < 2" in w for w in dwarn_e))

# 입력 후보 3개인데 미충족 → 제외 없이 기존 경로 (기사별 1개 생략 → warning만)
cmap3 = _collected_map(("https://a.com/4", "2배 성장, 30% 증가, 10억 투자 유치"))
issue_noexcuse = {
    "date": "2026-10-15", "briefing": [],
    "analysis": [_analysis_with_source("https://a.com/4")],  # 후보 3개 ≥ 2
}
derr_n, dwarn_n = check_depth(issue_noexcuse, cmap3)
ok("후보 충분시 제외 안 됨", not any("numbers 슬롯 제외" in w for w in dwarn_n))
ok("후보 충분시 1개 생략 warning", any("슬롯 1개 생략 (numbers)" in w for w in dwarn_n))

# 3. 게이트 수학: 5개 analysis 중 3개 excused → 분모 22, 허용 3, 나머지 생략 1개 → PASS
cmap5 = _collected_map(
    ("https://a.com/1", "매출이 2배로 뛰었다"),  # 1개 → excused
    ("https://a.com/2", "숫자 없는 발표문이다"),  # 0개 → excused
    ("https://a.com/3", "정책 발표 소식이다"),    # 0개 → excused
)
analyses5 = [
    _analysis_with_source("https://a.com/1"),
    _analysis_with_source("https://a.com/2"),
    _analysis_with_source("https://a.com/3"),
    _make_analysis(2),  # numbers 충족
    _make_analysis(0),  # numbers만 미충족 (sources 기본값 → 조인 불가 → 카운트됨)
]
issue5 = {"date": "2026-10-15", "briefing": [], "analysis": analyses5}
derr5, dwarn5 = check_depth(issue5, cmap5)
# 분모 25-3=22, 허용 max(2, ceil(22*0.1))=3. 카운트된 미충족: numbers 1개 ≤ 3 → PASS
ok("게이트 수학: 5개 중 3개 excused → PASS", not any("전체 슬롯 생략" in e for e in derr5))
ok("excused warning 3개", sum(1 for w in dwarn5 if "numbers 슬롯 제외" in w) == 3)

# 4. 하위 호환: check_depth(issue) 인자 생략 → collected_by_url=None → 기존과 동일 동작
derr_compat, _ = check_depth(issue_2missing)  # P1 테스트의 2개 생략 케이스
ok("하위 호환: 인자 생략시 P1 동작 유지", not any("전체 슬롯 생략" in e for e in derr_compat))

# 유사도 함수 ---
ok("overlap 포함관계", _overlap(_normalize_sim("엔비디아가 새로운 AI 칩을 발표했다"), _normalize_sim("엔비디아가 새로운 AI 칩을 발표했다 추가")) > 0.8)
ok("jaccard 다름", _jaccard(_normalize_sim("완전히 다른 문장입니다"), _normalize_sim("전혀 겹치지 않는 내용")) < 0.3)

# --- P3: 소스 쿼터 게이트 ---
ok("extract_domain www 제거", extract_domain("https://www.techcrunch.com/2026/10/15/x") == "techcrunch.com")
ok("extract_domain 소문자화", extract_domain("https://TechCrunch.com/x") == "techcrunch.com")
ok("extract_domain 실패시 빈 문자열", extract_domain("not a url") == "")

def _quota_issue(domains):
    return {"analysis": [
        {"sources": [{"url": f"https://{d}/2026/10/15/a{i}"}]} for i, d in enumerate(domains)
    ]}

# 1. 통과: 4개 analysis, 도메인 각 1개씩 (최대 점유율 25%)
qerr, qwarn = check_source_quota(_quota_issue(["a.com", "b.com", "c.com", "d.com"]))
ok("quota 통과: 균등 분산", not qerr and not qwarn)

# 2. 실패: 3개 analysis 전부 같은 도메인 (100% > 50%)
qerr, qwarn = check_source_quota(_quota_issue(["a.com", "a.com", "a.com"]))
ok("quota 실패: 3개 독점 → QUOTA-001", any("QUOTA-001" in e for e in qerr))

# 3. 50% 경계: error 없음, QUOTA-002 warning만
qerr, qwarn = check_source_quota(_quota_issue(["a.com", "a.com", "b.com", "b.com"]))
ok("quota 50% 경계: error 없음", not qerr)
ok("quota 50% 경계: QUOTA-002 warning", any("QUOTA-002" in w for w in qwarn))

# 4. 실패: 75% 독점 (50% 초과)
qerr, qwarn = check_source_quota(_quota_issue(["a.com", "a.com", "a.com", "b.com"]))
ok("quota 실패: 75% 독점 → QUOTA-001", any("QUOTA-001" in e for e in qerr))

# --- P3: 시사점 뼈대 템플릿 게이트 ---
def _tpl_issue(takeaways):
    return {"analysis": [{"takeaway": tw} for tw in takeaways]}

TW_A1 = "응답 속도가 2배 빨라진 것이 이번 모델 경쟁의 의미입니다. 담당자는 영어 외 과제 점수를 잡아 보면 됩니다."
TW_A2 = "가격이 30% 낮아진 것이 이번 시장 재편의 의미입니다. 기획자는 경쟁사 가격표를 올려 보면 됩니다."
TW_A3 = "도입 사례가 늘어난 것이 이번 기술 확산의 의미입니다. 실무자는 사내 파일럿으로 시험해 보면 됩니다."
TW_B = "시장이 빠르게 변하고 있습니다. 우리는 대응 전략을 세워야 합니다."

ok("skeleton 추출", _takeaway_skeleton(TW_A1) == "것이이번□의의미입니다‖□보면됩니다")
ok("skeleton 미매칭 → 빈 문자열", _takeaway_skeleton(TW_B) == "")

# 1. 3개 반복 → error
terr, twarn = check_takeaway_template(_tpl_issue([TW_A1, TW_A2, TW_A3]))
ok("takeaway-tpl 3개 반복 → error", any("TAKEAWAY-TPL" in e for e in terr))

# 2. 정상 통과
terr, twarn = check_takeaway_template(_tpl_issue([TW_B, "완전히 다른 시사점입니다. 다른 행동을 해야 합니다."]))
ok("takeaway-tpl 정상 통과", not terr and not any("TAKEAWAY-TPL" in w for w in twarn))

# 3. 2개 반복 → warning
terr, twarn = check_takeaway_template(_tpl_issue([TW_A1, TW_A2, TW_B]))
ok("takeaway-tpl 2개 → error 없음", not terr)
ok("takeaway-tpl 2개 → warning", any("TAKEAWAY-TPL" in w for w in twarn))

# --- P4: 도메인 기준 중복 제거 (select_buckets) ---
from datetime import datetime, timezone, timedelta

_P4_NOW = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

ok("bucket_domain: www 제거", bucket_domain([{"url": "https://www.openai.com/a"}]) == "openai.com")
ok("bucket_domain: 서브도메인 유지", bucket_domain([{"url": "https://blog.openai.com/a"}]) == "blog.openai.com")
ok("bucket_domain: 빈 items", bucket_domain([]) == "")
ok("bucket_domain: URL 없음", bucket_domain([{"title": "t"}]) == "")
ok("bucket_domain: validate.extract_domain과 동일",
   bucket_domain([{"url": "https://WWW.Example.COM/x"}]) == extract_domain("https://WWW.Example.COM/x"))

def _scored(name, url, source):
    # score_bucket을 통과하도록(5점 이상) 현실적인 아이템 구성
    items = [{"title": f"OpenAI GPT 발표 {name}", "summary": "성능이 30% 향상됨",
              "url": url, "source": source, "published": _P4_NOW}]
    return (name, items)

# 도메인 중복 제거 (fallback 미발동: 도메인 필터 후 main >= MIN_MAIN)
_mixed = [
    _scored("a1", "https://openai.com/a", "라벨1"),
    _scored("a2", "https://openai.com/b", "라벨2"),
    _scored("a3", "https://openai.com/c", "라벨3"),
    _scored("b1", "https://anthropic.com/x", "라벨4"),
    _scored("c1", "https://google.com/y", "라벨5"),
    _scored("d1", "https://nvidia.com/z", "라벨6"),
]
main, rest = select_buckets(_mixed)
_main_names = {m[0] for m in main}
ok("도메인 중복 제거: 같은 도메인은 1개만 main",
   "a1" in _main_names and "a2" not in _main_names and "a3" not in _main_names)
ok("도메인 중복 제거: 다른 도메인은 모두 main",
   all(n in _main_names for n in ["b1", "c1", "d1"]))
ok("도메인 중복 제거: 탈락분은 rest", len(rest) == 2)

# fallback: 도메인이 부족하면 MIN_MAIN까지 채워짐 (도메인 규칙 완화)
_same_dom = [
    _scored("t1", "https://openai.com/a", "OpenAI Blog"),
    _scored("t2", "https://openai.com/b", "OpenAI News"),
    _scored("t3", "https://openai.com/c", "OpenAI Research"),
]
main, rest = select_buckets(_same_dom)
ok("fallback: 도메인 부족 시 MIN_MAIN까지 채워짐", len(main) == MIN_MAIN)

# 서로 다른 도메인 → 모두 main (최대 MAX_MAIN)
_diff_dom = [
    _scored("t1", "https://openai.com/a", "OpenAI"),
    _scored("t2", "https://anthropic.com/b", "Anthropic"),
    _scored("t3", "https://google.com/c", "Google"),
    _scored("t4", "https://nvidia.com/d", "NVIDIA"),
]
main, rest = select_buckets(_diff_dom)
ok("도메인 분산: 4개 도메인 모두 main", len(main) == 4 and not rest)
ok("도메인 분산: score 포함 3-튜플", all(len(m) == 3 for m in main))

# fallback: 도메인이 2개뿐이어도 MIN_MAIN(3)까지 채워짐
main, rest = select_buckets(_same_dom)
ok("fallback: MIN_MAIN까지 채워짐", len(main) == MIN_MAIN)

# fallback: 피드 라벨 필터는 유지 (같은 라벨은 fallback에서도 제외)
_label_same = [
    _scored("t1", "https://openai.com/a", "동일라벨"),
    _scored("t2", "https://openai.com/b", "동일라벨"),
    _scored("t3", "https://openai.com/c", "동일라벨"),
]
main, rest = select_buckets(_label_same)
ok("fallback: 피드 라벨 필터 유지", len(main) == 1)

# MAX_MAIN 상한 유지
_many = [_scored(f"t{i}", f"https://dom{i}.com/a", f"소스{i}") for i in range(8)]
main, rest = select_buckets(_many)
ok("MAX_MAIN 상한", len(main) == MAX_MAIN and len(rest) == 8 - MAX_MAIN)

# LLM 경로 배선: draft.py main()이 select_buckets를 호출하는지 소스 레벨 확인
_draft_src = (Path(__file__).resolve().parents[1] / "draft.py").read_text(encoding="utf-8")
ok("LLM 경로 배선: main()에서 select_buckets 호출",
   "main_buckets, rest_buckets = select_buckets(ranked)" in _draft_src)
ok("LLM 경로 배선: payload에 main_topics 포함", '"main_topics"' in _draft_src)
ok("LLM 경로 배선: 프롬프트 하드 규칙 포함", "main_topics에 없는 토픽으로는 analysis를 만들지 않는다" in _draft_src)

# ---------------------------------------------------------------------------
# P5: 수집 단계 개선 — <source url> 파싱, origin_url 우선, 48h 신선도 필터
# ---------------------------------------------------------------------------
from collect import parse_feed, FRESHNESS_HOURS, FEED_LIMITS

_GNEWS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News AI</title>
<item>
  <title>OpenAI launches new agent model with 70B parameters</title>
  <link>https://news.google.com/rss/articles/CBMiXmh0dHBzOi8vd3d3LnRoZXZlcmdllmNvbS9hLXRlc3TSAQA?oc=5</link>
  <source url="https://www.theverge.com/">The Verge</source>
  <pubDate>Thu, 16 Oct 2026 00:30:00 GMT</pubDate>
  <description>OpenAI announced a 70B parameter agent model today.</description>
</item>
<item>
  <title>Anthropic news without source tag</title>
  <link>https://news.google.com/rss/articles/CBMiYmh0dHBzOi8vYW50aHJvcGljLmNvbS9uZXdzL2E?oc=5</link>
  <pubDate>Thu, 16 Oct 2026 01:00:00 GMT</pubDate>
  <description>Anthropic published a safety update.</description>
</item>
</channel></rss>"""

_gnews_items = parse_feed(_GNEWS_XML, "Google News AI", "doc")
ok("P5: <source url> 파싱 — origin_url 저장",
   len(_gnews_items) == 2 and _gnews_items[0].get("origin_url") == "https://www.theverge.com/")
ok("P5: <source url> 없음 — origin_url 키 없음",
   "origin_url" not in _gnews_items[1])

# origin_url 우선 도메인 계산
ok("P5: bucket_domain이 origin_url 우선",
   bucket_domain([{"url": "https://news.google.com/rss/articles/xxx",
                   "origin_url": "https://www.theverge.com/"}]) == "theverge.com")
ok("P5: bucket_domain origin_url 없으면 url 사용",
   bucket_domain([{"url": "https://openai.com/news/a"}]) == "openai.com")

# check_source_quota: origin_url 기준 집계
from validate import check_source_quota as _csq

_q_issue = {"analysis": [
    {"sources": [{"url": "https://news.google.com/rss/articles/a", "origin_url": "https://www.theverge.com/"}]},
    {"sources": [{"url": "https://news.google.com/rss/articles/b", "origin_url": "https://techcrunch.com/2026/10/16/x"}]},
    {"sources": [{"url": "https://openai.com/news/c"}]},
]}
_q_err, _q_warn = _csq(_q_issue)
ok("P5: QUOTA — origin_url 기준이면 3개 도메인 분산으로 통과", not _q_err)

_q_issue2 = {"analysis": [
    {"sources": [{"url": "https://news.google.com/rss/articles/a", "origin_url": "https://openai.com/news/a"}]},
    {"sources": [{"url": "https://news.google.com/rss/articles/b", "origin_url": "https://openai.com/news/b"}]},
    {"sources": [{"url": "https://openai.com/news/c"}]},
]}
_q_err2, _ = _csq(_q_issue2)
ok("P5: QUOTA — origin_url이 openai.com이면 3/3 독점으로 차단",
   any("QUOTA-001" in e and "openai.com" in e for e in _q_err2))

# collected_by_url 조인 fallback: origin_url이 source dict에 없어도 수집 스냅샷에서 해소
from validate import url_core as _uc
_cbu = {_uc("https://news.google.com/rss/articles/a"):
        {"url": "https://news.google.com/rss/articles/a",
         "origin_url": "https://www.theverge.com/"}}
_q_err3, _ = _csq({"analysis": [
    {"sources": [{"url": "https://news.google.com/rss/articles/a"}]},
    {"sources": [{"url": "https://techcrunch.com/2026/10/16/y"}]},
]}, _cbu)
ok("P5: QUOTA — collected_by_url 조인으로 origin_url 해소", not _q_err3)

# GNews 조건: "Anthropic GNews"도 AI 힌트 없이 수집 필터 통과 ("GNews" in source 분기)
_gnews2 = parse_feed(
    b'<rss version="2.0"><channel><item><title>Quarterly earnings beat expectations</title>'
    b'<link>https://news.google.com/rss/articles/z</link>'
    b'<description>Revenue grew last quarter.</description></item></channel></rss>',
    "Anthropic GNews", "doc")
ok("P5: 'Anthropic GNews'도 수집 필터 통과", len(_gnews2) == 1)

# FEED_LIMITS: Google News AI 100
ok("P5: Google News AI limit 100", FEED_LIMITS.get("Google News AI") == 100)
ok("P5: FRESHNESS_HOURS 48", FRESHNESS_HOURS == 48)

# --- P6: 소스-주제 정합성 (SRC-REL) ---
from validate import check_source_relevance, _irrelevant_source_domains, _topic_companies


def _rel(title, *srcs):
    base = base_issue()["analysis"][0]
    return {**base, "id": "r1", "title": title,
            "sources": [{"handle": h, "url": u, "kind": "doc"} for h, u in srcs]}


# 1. google-pilot 재현: 구글 주제 + openai.com 소스 전부 → SRC-REL-001 보류
_p6a = base_issue(analysis=[_rel("구글, 뉴스 AI 파트너십 파일럿 400개 매체로 확대",
    ("Google News AI", "https://openai.com/a"), ("OpenAI News", "https://openai.com/b"))])
_p6h, _p6w = check_source_relevance(_p6a)
ok("P6: SRC-REL-001 보류 발생", any("SRC-REL-001" in h for h in _p6h))
ok("P6: SRC-REL-001은 holds (자동 탈락 아님)", len(_p6h) == 1 and not _p6w)

# 2. 라벨 불일치: Hacker News 라벨 + github URL → SRC-REL-101 보류
_p6b = base_issue(analysis=[_rel("AI 에이전트 프레임워크 비교",
    ("Hacker News", "https://github.com/user/repo"))])
_p6h2, _ = check_source_relevance(_p6b)
ok("P6: SRC-REL-101 보류 발생", any("SRC-REL-101" in h for h in _p6h2))

# 3. 정상 매칭: 구글 주제 + google.com/blog.google → 무플래그
_p6c = base_issue(analysis=[_rel("구글, 제미나이 3 공개",
    ("Google Blog", "https://blog.google/a"), ("Google", "https://google.com/b"))])
ok("P6: 정상 매칭 통과", check_source_relevance(_p6c) == ([], []))

# 4. 중립 매체: 구글 주제 + techcrunch → 무플래그
_p6d = base_issue(analysis=[_rel("구글, 제미나이 3 공개",
    ("TechCrunch", "https://techcrunch.com/a"))])
ok("P6: 중립 매체 통과", check_source_relevance(_p6d) == ([], []))

# 5. 비교 기사 면제: 회사 2개 → 스킵
ok("P6: X2 면제 (2개 회사)", _topic_companies("OpenAI와 구글이 손잡았다") is None)
_p6e = base_issue(analysis=[_rel("OpenAI와 구글이 손잡았다",
    ("OpenAI", "https://openai.com/a"))])
ok("P6: 비교 기사 무플래그", check_source_relevance(_p6e) == ([], []))

# 6. X1/X3 면제: 회사명 없음·동향형 → 스킵
ok("P6: X1 면제 (회사명 없음)", _topic_companies("AI 에이전트 시장 동향") is None)
ok("P6: X3 면제 (동향형)", _topic_companies("구글발 AI 동향 정리") is None)

# 7. 혼재: 구글 주제 + openai.com + techcrunch → SRC-REL-002 warning
_p6f = base_issue(analysis=[_rel("구글, 제미나이 3 공개",
    ("OpenAI", "https://openai.com/a"), ("TechCrunch", "https://techcrunch.com/b"))])
_p6h7, _p6w7 = check_source_relevance(_p6f)
ok("P6: SRC-REL-002 warning 발생", not _p6h7 and any("SRC-REL-002" in w for w in _p6w7))

# 8. QUOTA 분모 제외: 무관 소스 제외 후 QUOTA-001 미발동
_p6g = {"analysis": [
    _rel("구글, 뉴스 AI 파트너십 확대", ("X", "https://openai.com/a")),
    _rel("구글 클라우드 요금제 변경", ("X", "https://openai.com/b")),
    _rel("구글 딥마인드 논문", ("X", "https://openai.com/c")),
]}
_ex8 = _irrelevant_source_domains(_p6g)
ok("P6: 무관 도메인 3건 식별", len(_ex8) == 3)
ok("P6: QUOTA — 제외 후 미발동", not _csq(_p6g, exclude=_ex8)[0])
ok("P6: QUOTA — 제외 없으면 기존대로 발동", any("QUOTA-001" in e for e in _csq(_p6g)[0]))

# 9. 라벨 불일치 소스는 QUOTA 제외 대상 아님 (별도 문제)
_ex9 = _irrelevant_source_domains(_p6b)
ok("P6: 라벨 불일치는 QUOTA 제외 안 함", len(_ex9) == 0)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
