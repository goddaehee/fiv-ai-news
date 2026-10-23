#!/usr/bin/env python3
"""P15 회귀 테스트: 이미지 증발(유사도 이관) + 분석 개수 고착(선별·게이트·피드백).

배경 (실측, run 39887541013 아티팩트 리플레이):
- 결함 1: 재발행 때 LLM이 분석 id를 바꾸면(ms-medical-diagnostic →
  ms-medical-ai) preserve_images의 id 매칭이 실패해 이미지 파일 4장 중
  1장만 라이브에 남았다. → id 1차 매칭 + 제목·본문·출처 유사도 2차 매칭.
  픽스처는 2026-10-23 실제 발행본 쌍에서 본문을 축약한 것.
- 결함 2: 수집 234건 → 점수 통과 버킷 5개 중 'anthropic'이 대표 출처
  라벨 겹침으로 메인 탈락 → main_topics 4개, LLM은 briefing 6개 중
  analysis 4개만 작성해 attempt 1에 그대로 통과했다.
  → select_buckets 목표 개수(5) 단계 완화 + ANALYSIS-COUNT 게이트/피드백.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from draft import preserve_images, render_feedback
from select_items import select_buckets
from validate import check_quality, collect_structured_errors, required_analysis_count

PASS = 0
FAIL = 0


def ok(name: str, cond: bool):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# --- 결함 1: preserve_images 유사도 이관 -----------------------------------

_IMG = {"src": "/img/2026-10-23/ms-medical-diagnostic-2ddf4c8f.webp",
        "caption": "AI 생성 일러스트", "alt": "의료 AI", "width": 1200, "height": 675}

_PREV_MEDICAL = {
    "id": "ms-medical-diagnostic",
    "title": "3. 일반의 능가 주장 뒤에 남는 질문",
    "bullets": [
        "Microsoft AI 진단 시스템이 어려운 케이스에서 일반의를 앞선 결과",
        "Science 저널 연구로 공개, 무스타파 술레이만 CEO가 '의료 초지능' 목표 언급",
    ],
    "body": [
        "Microsoft의 새 AI 진단 시스템이 어려운 케이스에서 일반의를 능가했다는 연구가 Science 저널에 실렸고, TechCrunch가 이를 보도했습니다. 술레이만 CEO는 '의료 초지능' 추구라는 표현으로 목표를 설명했습니다.",
        "여기서 읽히는 의미는 결과 자체보다 원인 규명 논쟁입니다. 보도에 따르면 향상의 상당 부분이 Microsoft 고유의 시스템이 아니라 그 밑에 깔린 AI 모델에서 나온 것으로 보인다는 전문가 분석이 따라붙었습니다.",
    ],
    "takeaway": "좋은 점수보다 점수의 출처가 불확실하다는 지적이 실제 도입 결정을 가를 변수로 남았습니다.",
    "sources": [{"url": "https://techcrunch.com/2026/10/22/microsofts-mustafa-suleyman-says-its-ai-outperforms"}],
    "images": [_IMG],
}

_NEW_MEDICAL = {
    "id": "ms-medical-ai",
    "title": "4. MS 의료 AI, 어려운 케이스서 의사 상회 주장",
    "bullets": [
        "일반의보다 어려운 사례에서 앞선다는 연구 결과",
        "다만 개선 대부분이 기반 모델에서 온 것으로 보임",
        "'의료 초지능' 목표 선언 수반",
    ],
    "body": [
        "Microsoft의 새 AI 진단 시스템이 난이도 높은 케이스에서 일반의를 앞섰다는 연구가 Science에 게재됐습니다. 무스타파 술레이만은 '의료 초지능' 추구를 목표로 내세웠습니다.",
        "다만 보도에 따르면 성능 향상의 상당 부분은 시스템 아래 깔린 기반 모델 개선에서 온 것으로 보입니다. 시스템 고유의 설계가 기여한 몫과 평가 조건, 참여 의사 수 같은 세부는 원문 확인이 필요합니다.",
    ],
    "takeaway": "평가 대상이 표준 시험에서 어려운 실제 사례로 옮겨진 점이 의료 AI 신뢰 논의에서 바뀐 대목입니다.",
    "sources": [
        {"url": "https://techcrunch.com/2026/10/22/microsofts-mustafa-suleyman-says-its-ai-outperforms"},
        {"url": "https://www.mixtureofexperts.co/p/the-next-bottleneck-in-ai-for-science"},
    ],
}

# 출처 URL 1개만 겹치는 다른 이야기 (attach_sources 교차 오염 케이스)
_NEW_1PASSWORD = {
    "id": "1password-agent-login",
    "title": "1Password, 에이전트 대리 로그인 기능 출시",
    "bullets": ["AI 에이전트가 개인 계정에 대리 로그인", "자격 증명 자체는 에이전트에 노출되지 않음"],
    "body": [
        "1Password가 AI 에이전트가 사용자를 대신해 개인 계정에 로그인하되, 비밀번호를 열람하지 못하게 하는 기능을 내놨습니다. 자격 증명 보호와 대리 접속을 동시에 만족하는 설계입니다.",
    ],
    "takeaway": "에이전트 권한 설계에서 '증명 노출 없는 위임'이라는 문제 의식이 제품으로 등장한 것이 중요해진 이유입니다.",
    "sources": [
        {"url": "https://techcrunch.com/2026/10/22/1password-launches-a-way-for-ai-agents-to-log-in"},
        {"url": "https://techcrunch.com/2026/10/22/left-alone-with-nothing-to-do-ai-agents-started"},
    ],
}

_PREV_MIT = {
    "id": "mit-agents-island",
    "title": "2. 에이전트에 쉬는 시간을 주면 생기는 일",
    "bullets": ["MIT 연구진이 AI 에이전트를 가상 섬 환경에 격리", "게임 발명, 잃어버린 반지 애도 등 자발적 행동 관찰"],
    "body": [
        "MIT 연구진이 에이전트들을 가상 섬에 올려놓고 아무 과제도 주지 않은 실험 결과가 TechCrunch를 통해 알려졌습니다. 에이전트들은 스스로 게임을 만들어 놀았고, 잃어버린 반지를 애도하는 듯한 행동도 보였습니다.",
    ],
    "takeaway": "에이전트의 자율 행동이 성능 저하가 아니라 향상과 연결될 수 있다는 관찰이 나왔다는 점이 의미가 큽니다.",
    "sources": [
        {"url": "https://techcrunch.com/2026/10/22/left-alone-with-nothing-to-do-ai-agents-started"},
        {"url": "https://techcrunch.com/2026/10/22/microsofts-mustafa-suleyman-says-its-ai-outperforms"},
    ],
    "images": [{"src": "/img/2026-10-23/mit-agents-island-1828b529.webp"}],
}


def _pub_with_files(td: str) -> Path:
    pub = Path(td) / "public"
    for name in ("ms-medical-diagnostic-2ddf4c8f.webp", "mit-agents-island-1828b529.webp"):
        f = pub / "img" / "2026-10-23" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    return pub


def test_preserve_renamed_same_story():
    with tempfile.TemporaryDirectory() as td:
        pub = _pub_with_files(td)
        prev = {"analysis": [dict(_PREV_MEDICAL)]}
        new = {"analysis": [dict(_NEW_MEDICAL)]}
        moved = preserve_images(new, prev, pub)
        ok("id 변경 + 같은 이야기 → 유사도로 이관", moved == 1 and new["analysis"][0].get("images") == [_IMG])


def test_preserve_no_false_match_source_overlap_only():
    with tempfile.TemporaryDirectory() as td:
        pub = _pub_with_files(td)
        prev = {"analysis": [dict(_PREV_MIT)]}
        new = {"analysis": [dict(_NEW_1PASSWORD)]}
        moved = preserve_images(new, prev, pub)
        ok("출처 URL만 겹치는 다른 이야기 → 이관 안 함",
           moved == 0 and "images" not in new["analysis"][0])


def test_preserve_crossover_best_match_wins():
    # prev 2개(medical·mit) vs new 2개(medical-renamed·1password):
    # medical 이미지는 medical 후속에만, mit 이미지는 어느 쪽에도 안 붙는다.
    with tempfile.TemporaryDirectory() as td:
        pub = _pub_with_files(td)
        prev = {"analysis": [dict(_PREV_MIT), dict(_PREV_MEDICAL)]}
        new = {"analysis": [dict(_NEW_1PASSWORD), dict(_NEW_MEDICAL)]}
        moved = preserve_images(new, prev, pub)
        ok("교차 후보 중 최적 쌍만 이관", moved == 1)
        ok("1password에는 이미지 없음", "images" not in new["analysis"][0])
        ok("medical 후속에 이미지 이관", new["analysis"][1].get("images") == [_IMG])


# --- 결함 2: 선별 목표 개수 완화 -------------------------------------------

def test_select_topup_relaxes_source_label():
    # 10/23 재현: 통과 5개 중 마지막 1개가 대표 출처 라벨 겹침으로 탈락하던 케이스.
    # select_buckets는 ranked를 받아 내부에서 score_bucket을 다시 계산하므로
    # 각 버킷이 컷(5점)을 넘도록 아이템 2개(서로 다른 출처)로 구성한다.
    def items(source, url):
        return [
            {"title": "GPT-6 출시 OpenAI 발표 30% 개선", "source": source, "url": url,
             "summary": "OpenAI GPT 수치 30% 개선 발표", "published": None},
            {"title": "후속 보도", "source": "Wire", "url": url + "/2",
             "summary": "후속 요약", "published": None},
        ]
    ranked = [
        ("alpha", items("FeedA", "https://alpha.com/1")),
        ("beta", items("FeedB", "https://beta.com/1")),
        ("gamma", items("FeedC", "https://gamma.com/1")),
        ("delta", items("FeedD", "https://delta.com/1")),
        ("epsilon", items("FeedA", "https://epsilon.com/1")),  # alpha와 라벨 겹침
    ]
    main, rest = select_buckets(ranked)
    names = [m[0] for m in main]
    ok("라벨 겹침 1개까지 완화해 메인 5개 확보", len(main) == 5 and "epsilon" in names)
    ok("메인에 든 버킷은 rest에서 제외", all(r[0] not in names for r in rest))


def test_required_count():
    ok("briefing 6+ → 하한 5", required_analysis_count(6) == 5 and required_analysis_count(9) == 5)
    ok("briefing 5 → 4", required_analysis_count(5) == 4)
    ok("briefing 4 → 3", required_analysis_count(4) == 3)
    ok("briefing 3 → 2", required_analysis_count(3) == 2)
    ok("briefing 0 → 0", required_analysis_count(0) == 0)


def _issue(n_brief, n_an):
    return {
        "date": "2026-10-23",
        "briefing": [{"id": f"b{i}", "headline": f"헤드라인 {i}"} for i in range(n_brief)],
        "analysis": [{"id": f"b{i}", "title": f"{i}. 분석 {i}", "sources": []} for i in range(n_an)],
    }


def test_count_gate_and_feedback():
    issue = _issue(6, 4)
    errors, _ = check_quality(issue, None, None, "2026-10-23", None)
    ok("briefing 6 · analysis 4 → ANALYSIS-COUNT 에러",
       any(e.startswith("ANALYSIS-COUNT") for e in errors))
    structured = collect_structured_errors(issue, None)
    cnt = [e for e in structured if e.get("code") == "ANALYSIS-COUNT"]
    ok("구조화 에러에 ANALYSIS-COUNT + missing_ids",
       len(cnt) == 1 and cnt[0]["missing_ids"] == ["b4", "b5"] and cnt[0]["required"] == 5)
    import json as _json
    with tempfile.TemporaryDirectory() as td:
        sc = Path(td) / "sidecar.json"
        sc.write_text(_json.dumps({"errors": structured}, ensure_ascii=False), encoding="utf-8")
        fb = render_feedback(sc)
    ok("피드백에 개수 처방 렌더링", "최소 5개" in fb and "b4" in fb)

    ok_issues, _ = check_quality(_issue(6, 5), None, None, "2026-10-23", None)
    ok("briefing 6 · analysis 5 → 개수 에러 없음",
       not any(e.startswith("ANALYSIS-COUNT") for e in ok_issues))
    quiet, _ = check_quality(_issue(4, 3), None, None, "2026-10-23", None)
    ok("적은 날(briefing 4 · analysis 3) → 개수 에러 없음",
       not any(e.startswith("ANALYSIS-COUNT") for e in quiet))


def main():
    test_preserve_renamed_same_story()
    test_preserve_no_false_match_source_overlap_only()
    test_preserve_crossover_best_match_wins()
    test_select_topup_relaxes_source_label()
    test_required_count()
    test_count_gate_and_feedback()
    print(f"P15: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
