#!/usr/bin/env python3
"""2026-09-17 rewrite to house voice. Public facts only, original Korean."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _editorial import A, AN, AN_DOC, B, K, METHOD, OA, OA_DOC, S, TIP, TL, dump

JEV = S("TypeSafe AI", "https://typesafe.ai/blog/introducing-system-one-models-and-jev", "doc")
DEC = S("The Decoder", "https://the-decoder.com/former-openai-researcher-builds-an-ai-model-that-judges-options-instead-of-writing-text/", "doc")
CLAUDE = S("Anthropic", "https://claude.com/blog/cowork-is-now-claude", "doc")
TC = S("TechCrunch", "https://techcrunch.com/2026/09/16/anthropic-merges-claude-chat-and-cowork-in-one-interface/", "doc")
ADS = S("OpenAI", "https://openai.com/index/reimagining-advertising-with-ai/", "doc")
REU = S("Reuters", "https://www.reuters.com/business/media-telecom/openai-tests-advertiser-sponsored-agents-expands-ai-tools-chatgpt-ads-2026-09-16/", "doc")
MOZ = S("Mozilla", "https://blog.mozilla.org/en/firefox/mozilla-mistral-partnership/", "doc")
NOUS = S("Nous Research", "https://nousresearch.com/refactoring-hermes-with-1393-agents/", "doc")
MAI = S("Microsoft AI", "https://microsoft.ai/news/mai-code-of-conduct/", "doc")
REU2 = S("Reuters", "https://www.reuters.com/business/microsoft-ai-chief-calls-out-anthropics-approach-to-ai-consciousness-2026-09-16/", "doc")
TOM = S("Tom's Hardware", "https://www.tomshardware.com/tech-industry/artificial-intelligence/defeated-gpt-6-astra-model-spent-several-hours-just-farming-potatoes-after-being-blown-up-by-a-creeper-in-minecraft-openai-offering-gets-further-than-any-other-ai-system-in-141-hour-test", "doc")
BENZ = S(
    "Benzinga",
    "https://www.benzinga.com/markets/tech/26/09/61807324/mark-zuckerberg-meta-muse-ai-safety-delayed-months-ai-labs-responsibility",
    "doc",
)

issue = {
    "date": "2026-09-17",
    "title": "판단만 하는 Jev · Claude 한 화면 · 141시간 마인크래프트",
    "heroline": "글을 쓰지 않는 모델이 가격표를 열었다",
    "dek": "TypeSafe AI가 선택지만 점수로 받는 Jev를 대기자 명단으로 열었고, Anthropic은 Cowork를 채팅에 합쳤습니다. 같은 타임라인에 GPT-6 Astra의 141시간 마인크래프트와 Muse를 몇 달 미룬 Meta의 글이 올라왔습니다.",
    "tag": "판단모델",
    "briefMin": 5,
    "readMin": 18,
    "keywords": ["Jev", "Claude Docs", "Sponsored Agents", "Hermes Agent", "Muse"],
    "mainEvent": "TypeSafe AI가 글을 쓰지 않고 판단만 돌려주는 모델 Jev를 열며, 입력 100만 토큰당 $0.042에 출력은 무료라는 가격을 붙였습니다.",
    "briefing": [
        B("jev", "TypeSafe AI가 텍스트를 만들지 않는 모델 Jev를 공개했다 — 입력 100만 토큰 $0.042, 출력은 무료",
          "정해진 선택지에 점수·확률을 붙입니다. 대기자 명단 얼리 액세스입니다. 20~200배라는 비교는 회사 워크플로 값입니다."),
        B("muse", "Zuckerberg가 Muse 출시를 몇 달 미뤘고, 남에게 멈추라고 하지는 않았다고 적었다",
          "Meta는 에이전트 Muse를 안전 이유로 미뤘다고 했습니다. 업계 전체 감속 요구와 선을 그은 글입니다."),
        B("minecraft", "Vals AI가 GPT-6 Astra의 마인크래프트 141시간을 공개했다 — 엔더 진주 3개 뒤 크리퍼에 날아갔다",
          "블레즈 농장과 진주 3개까지 갔다가, 상자·침대가 터진 뒤에는 감자 농사만 몇 시간 이어졌다고 적었습니다."),
        B("claude-merge", "Anthropic이 Cowork와 채팅을 하나의 Claude로 합치고 Docs·Slides를 베타로 열었다",
          "Pro·Max부터 몇 주에 걸쳐 웹·데스크톱·모바일에 올라갑니다. 어디에 넣을지 고르지 않아도 됩니다."),
        B("ads", "OpenAI가 ChatGPT에 Sponsored Agents를 시험하고 광고 도구를 넓힌다",
          "광고를 누른 뒤 사업자 후원 에이전트와 라벨이 붙은 별도 대화를 엽니다. 미국 일부 광고주 시험입니다."),
        B("firefox", "Mozilla가 Mistral Small 4를 Firefox Smart Window 베타에 넣는다",
          "미국·캐나다에 이어 프랑스가 열립니다. Mozilla는 대화를 기본으로 서버에 남기지 않고, Mistral은 제로 리텐션에 동의했다고 적었습니다."),
        B("hermes", "Nous Research가 서브에이전트 1,393개로 파이썬을 34.4% 줄인 결과를 공개했다",
          "19시간, 동시 최대 218개입니다. 테스트 제외 파이썬이 1,063,826줄에서 698,363줄로 줄었다고 적었습니다."),
        B("welfare", "Mustafa Suleyman이 모델 복지를 반박했다 — AI는 권리도 법인격도 가져선 안 된다",
          "Microsoft AI 행동강령 초안입니다. Claude 훈련 문서의 의식 언어가 종료를 어렵게 만든다고 적었습니다."),
        B("extras", "🆕 그 밖의 신기능·신제품",
          "브라우저 조수와 광고 대화가 같은 날의 작은 출시로 남습니다. 본문 하단에 짧게 모았습니다."),
    ],
    "keynums": [
        K("$0.042", "Jev 입력 100만 토큰", "출력 무료 · TypeSafe 발표"),
        K("70–500ms", "Jev 응답 시간", "회사 발표 구간"),
        K("141시간", "Astra 마인크래프트", "Vals AI 공개"),
        K("1,393개", "Hermes 서브에이전트", "19시간 · 동시 218"),
        K("34.4%", "파이썬 줄 감소", "1,063,826 → 698,363"),
        K("Pro·Max", "Claude 통합 우선", "Docs·Slides 베타"),
        K("미국", "Sponsored Agents 시험", "선택 광고주"),
        K("FR+NA", "Smart Window 베타", "Mistral Small 4"),
    ],
    "timeline": [
        TL("09-02", "Nous Research가 Hermes 서브에이전트 1,393개로 코드 정리를 돌렸다"),
        TL("09-14", "Microsoft AI가 Humanist AI 행동강령 초안을 협의용으로 열었다"),
        TL("09-15", "TypeSafe AI가 Jev 얼리 액세스를 열었다"),
        TL("09-15", "Vals AI가 Astra 마인크래프트 141시간 로그를 올렸다"),
        TL("09-15", "Zuckerberg가 Muse를 몇 달 미뤘다고 적었다"),
        TL("09-16", "Anthropic이 Cowork와 채팅을 합치고 Docs·Slides 베타를 열었다"),
        TL("09-16", "OpenAI가 Sponsored Agents와 광고 도구를 발표했다"),
        TL("09-16", "Mozilla가 Mistral Small 4를 Smart Window 베타에 넣는다고 밝혔다"),
    ],
    "intro": "글을 쓰지 않는 모델이 가격을 먼저 열었습니다. 같은 날 채팅과 에이전트 화면이 하나로 붙고, 긴 과제는 상자 하나가 터지자 몇 시간을 허비했습니다. 배수는 누가 어떤 워크플로에서 쟀는지를 앞에 두고 읽으면 됩니다.",
    "analysis": [
        A("jev", 1,
          "TypeSafe AI가 텍스트를 만들지 않는 모델 Jev를 공개했다 — 입력 100만 토큰 $0.042, 출력은 무료",
          [
            "개발자가 질문과 선택지를 정하면 점수·확률·신뢰도를 돌려줍니다.",
            "입력 100만 토큰 $0.042, 출력은 미터링하지 않는다고 적었습니다.",
            "창립자 Diogo Almeida는 InstructGPT 저자 중 한 명으로 소개됩니다.",
          ],
          [
            "TypeSafe AI는 9월 15일 첫 System One 모델 Jev를 대기자 명단으로 열었습니다. 토큰을 한 줄씩 쓰는 채팅 모델이 아니라, 보기 고르기·점수·예아니오 확률처럼 타입이 막힌 답을 한 번에 붙입니다. 회사는 병렬 샘플러와 Reinforcement Learning for Calibrated Decisions(RLCD)를 썼다고 적었습니다. 구조 밖 문장을 만들 수 없다고 말하지만, 허용된 보기 안의 오답은 그 문장이 커버하지 않습니다.",
            "가격은 입력 100만 토큰 $0.042, 출력 무료입니다. 지연은 70–500ms, LLM보다 20~200배 빠르고 40~400배 싸다는 비교는 회사가 만든 워크플로 기준입니다. 공개 리더보드와 아키텍처 논문은 아직 없습니다. 분류·라우팅처럼 정답을 나중에 확인할 수 있는 자리에 값싼 판정기를 붙일 때 대기자 명단을 보면 됩니다.",
          ],
          "분류·라우팅처럼 사후에 답을 확인할 수 있는 자리에 값싼 판정기를 붙일 때 대기자 명단을 보면 됩니다. 20~200배·40~400배는 회사 워크플로 값이라, 공개 리더보드가 나오기 전에는 그 배수로 단가를 적지 않는 편이 안전합니다.",
          ["Jev", "TypeSafe", "판단"],
          [JEV, DEC],
        ),
        A("muse", 2,
          "Zuckerberg가 Muse 출시를 몇 달 미뤘고, 남에게 멈추라고 하지는 않았다고 적었다",
          [
            "Meta는 에이전트 Muse를 안전·보안 이유로 몇 달 미뤘다고 했습니다.",
            "다른 랩에 먼저 멈추라고 하지 않고 자기 일정만 옮겼다고 적었습니다.",
            "업계 전체 감속 요구와 선을 그은 글입니다.",
          ],
          [
            "Mark Zuckerberg는 Muse 출시를 몇 달 미룬 이유를 안전과 보안으로 적었습니다. 다른 랩에 같은 속도를 요구하지 않았고, 일상 작업의 일부로 일정을 옮겼다고 했습니다. 감속을 산업 규칙으로 만들자는 쪽과, 랩마다 자기 속도로 맞추자는 쪽이 같은 주에 글을 올렸습니다.",
            "확인할 것은 Meta가 말한 지연의 기간과 범위입니다. 제품 로드맵 문장과 정치 인터뷰 문장은 같은 결론으로 묶지 말고, 출처만 분리해 두면 됩니다.",
          ],
          "속도를 늦추라는 요구에 랩마다 다른 답이 나왔습니다. Muse를 몇 달 미뤘다는 문장은 Meta의 글이고, 업계 전체 합의는 이 글만으로 확인되지 않습니다.",
          ["Muse", "Meta", "속도"],
          [BENZ],
        ),
        A("minecraft", 3,
          "Vals AI가 GPT-6 Astra의 마인크래프트 141시간을 공개했다 — 엔더 진주 3개 뒤 크리퍼에 날아갔다",
          [
            "141시간 동안 블레즈 농장과 엔더 진주 3개까지 갔다고 적었습니다.",
            "상자·침대가 크리퍼에 터진 뒤 감자 농사만 몇 시간 이어졌습니다.",
            "Vals AI는 이전 AI 시스템보다 멀리 갔다고 자기 테스트 기준으로 말했습니다.",
          ],
          [
            "독립 평가사 Vals AI는 GPT-6 Astra를 마인크래프트에 141시간 풀어 놓고 Twitch로 중계했습니다. 반자동 블레즈 농장, 블레이즈 막대 6개, 워프드 포레스트에서 엔더맨 6마리 이상, 엔더 진주 3개까지 갔다고 적었습니다. 귀중품을 상자에 넣은 뒤 크리퍼가 상자·침대를 날렸습니다.",
            "그다음 몇 시간은 감자 농사에 가깝습니다. 긴 과제에서 에이전트를 멈춘 것은 점수표의 천장보다 중간 상태를 어디에 두는지입니다. Vals가 ‘이전 어떤 AI보다 멀리’라고 한 비교는 자기 테스트 세트 기준이라, 다른 환경의 기록과 한 줄에 두지 않는 편이 안전합니다.",
          ],
          "긴 과제에서 에이전트를 멈춰 세운 것은 능력의 한계가 아니라 복구 설계입니다. 한 번의 사고가 전부를 날리지 않도록, 중간 산출물을 대화 밖 저장소에 두는 것부터 정하면 됩니다.",
          ["에이전트", "Minecraft", "Astra"],
          [TOM],
        ),
        A("claude-merge", 4,
          "Anthropic이 Cowork와 채팅을 하나의 Claude로 합치고 Docs·Slides를 베타로 열었다",
          [
            "어디에 넣을지 고르지 않아도 Cowork가 하던 일이 모든 대화에서 됩니다.",
            "Claude Docs와 Claude Slides는 유료 플랜 베타, 엔터프라이즈는 관리자가 켭니다.",
            "Pro·Max 웹·데스크톱·모바일부터 몇 주에 걸쳐 올라갑니다.",
          ],
          [
            "Anthropic은 9월 16일 Cowork와 채팅을 한 Claude로 합친다고 밝혔습니다. 큰 일은 Cowork, 질문은 채팅으로 나누던 선택이 사라집니다. 노트북을 닫아도 이어지고, Docs·Slides·Design이 같은 대화 안에 들어갑니다. 슬라이드는 바로 발표하거나 PowerPoint·PDF로 내릴 수 있습니다.",
            "한국 구독자에게는 새 모델보다 화면이 바뀌는 변화입니다. 기존 Cowork 작업·커넥터·스킬은 그대로 넘어온다고 적었습니다. 팀·무료는 이후이고, 엔터프라이즈는 관리자 스위치가 있습니다. Pro·Max를 쓰고 있다면 몇 주 안에 탭 구분이 사라지므로, 문서·슬라이드를 대화에서 부르는 쪽으로 옮겨 두면 됩니다.",
          ],
          "한국 구독자에게는 새 모델이 아니라 화면이 바뀌는 변화입니다. Pro·Max라면 몇 주 안에 Cowork 탭이 없어지므로, 문서와 슬라이드를 대화에서 여는 흐름으로 미리 옮겨 두는 편이 낫습니다.",
          ["Claude", "Cowork", "Docs"],
          [CLAUDE, TC, AN],
        ),
        A("ads", 5,
          "OpenAI가 ChatGPT에 Sponsored Agents를 시험하고 광고 도구를 넓힌다",
          [
            "광고를 본 뒤 사업자 후원 에이전트와 라벨이 붙은 별도 대화를 시작할 수 있습니다.",
            "이 대화는 ChatGPT의 독립 답변·원래 채팅과 분리된다고 적었습니다.",
            "HubSpot이 첫 CRM, Shopify가 첫 이커머스 파트너입니다.",
          ],
          [
            "OpenAI는 9월 16일 Sponsored Agents 시험과 광고 작성 도구를 열었습니다. 식탁 광고를 본 뒤 치수·관리법을 사업자 에이전트에게 묻는 그림입니다. Reuters가 같은 날 받아 전했습니다. 미국 일부 광고주 시험이고, Shopify 앱은 ChatGPT Ads가 열린 시장에 9월 23일부터 국제로 간다고 적었습니다.",
            "후원 대화는 독립 답변과 원래 창과 분리된다고 적었습니다. 유료 창이 광고에서 빠지는지는 화면에서 보면 됩니다. 브랜드 쪽이라면 HubSpot·Shopify 연동이 열린 오늘부터 ChatGPT를 검색 광고 지면처럼 다루면 됩니다.",
          ],
          "ChatGPT를 무료로 쓴다면 지금 창이 광고에서 시작됐는지 보면 됩니다. 후원 에이전트 대화와 독립 답변을 한 로그에 섞지 말고, 미국 시험 구간이라는 조건을 같이 적으면 됩니다.",
          ["광고", "OpenAI", "에이전트"],
          [ADS, REU, OA_DOC],
        ),
        A("firefox", 6,
          "Mozilla가 Mistral Small 4를 Firefox Smart Window 베타에 넣는다",
          [
            "미국·캐나다에 이어 프랑스가 공식 프랑스어로 열립니다.",
            "내장 모델이 여럿이고 가져오기(BYO)도 있다고 적었습니다.",
            "Mozilla는 대화를 기본으로 서버에 안 남기고, Mistral은 제로 리텐션에 동의했다고 했습니다.",
          ],
          [
            "Mozilla는 9월 16일 Mistral Small 4를 Firefox Smart Window 베타 모델로 넣는다고 밝혔습니다. 복잡한 검색 경로를 정리하고 닫았던 탭을 다시 집어 주는 브라우저 조수입니다. 영국·독일은 올해 후반 예정입니다.",
            "브라우저 AI 경쟁이 점수보다 데이터 보존과 모델 선택권에서 갈립니다. 한국 리전 일정은 이 발표에 없습니다. Firefox를 쓴다면 Smart Window의 기본값과 모델 선택 화면을 먼저 열어 두면 됩니다.",
          ],
          "브라우저 AI는 기본값과 모델 선택 화면을 먼저 열면 됩니다. Mozilla가 대화를 서버에 남기지 않고 Mistral이 제로 리텐션에 동의했다는 문장을, 한국 리전이 빠졌다는 사실과 같이 두면 됩니다.",
          ["Firefox", "Mistral", "프라이버시"],
          [MOZ],
        ),
        A("hermes", 7,
          "Nous Research가 서브에이전트 1,393개로 파이썬을 34.4% 줄인 결과를 공개했다",
          [
            "9월 2일부터 약 19시간, 동시 최대 218개입니다.",
            "테스트 제외 파이썬이 1,063,826줄에서 698,363줄로 줄었다고 적었습니다.",
            "메인 런 토큰 비용은 약 1만 9,300달러, 후속 포함 약 2만 5,000달러입니다.",
          ],
          [
            "Nous Research는 Hermes Agent에 서브에이전트 1,393개를 붙여 자기 코드베이스를 정리했다고 적었습니다. 테스트 제외 파이썬 1,063,826줄이 698,363줄이 됐고, 5,000줄이 넘는 파일은 37개에서 6개, 300줄이 넘는 함수는 192개에서 2개가 됐다고 표를 공개했습니다. gateway/run.py는 34,847줄에서 5,512줄입니다.",
            "1,393개를 규칙으로 읽지는 않습니다. 지우는 일이라 잘했는지 판정하기가 비교적 쉬운 과제였고, 사람 리뷰 시간은 비용에 넣지 않았습니다. 개수를 올리기 전에 삭제한 줄의 회귀 테스트를 저장소 밖에서 한 번 더 보면 됩니다.",
          ],
          "1,393개라는 숫자를 그대로 따라 할 규칙으로 읽지는 않습니다. 줄 수 34.4%는 자기 저장소의 삭제 작업 결과이고, 머지 전에 diff와 회귀를 사람 큐에 올리는 비용은 별도입니다.",
          ["Hermes", "에이전트", "리팩터"],
          [NOUS],
        ),
        A("welfare", 8,
          "Mustafa Suleyman이 모델 복지를 반박했다 — AI는 권리도 법인격도 가져선 안 된다",
          [
            "Microsoft AI 행동강령 초안은 공개 협의용입니다.",
            "AI에 권리·법인격을 주지 않는다고 적었습니다.",
            "Claude 훈련 문서의 의식 언어가 종료를 어렵게 만든다고 주장했습니다.",
          ],
          [
            "Microsoft AI의 Mustafa Suleyman은 9월 14일 Humanist AI 행동강령 초안을 열었습니다. 요지는 사람이 AI보다 먼저이고, 모델 복지는 틀렸으며, 코드와 작업이 충돌하면 작업을 실패로 둔다는 것입니다. Reuters는 같은 취지로 Claude 훈련에 의식 추측이 들어가면 끄기가 더 어려워진다고 전했습니다.",
            "모델 문서에 적힌 문구가 회사 사이 안전 정책 논쟁의 대상이 됐습니다. Anthropic의 공식 반박 여부는 이 초안만으로 확인되지 않습니다. 프런티어 랩의 가치관 차이가 공개 문서로 맞부딪힌 장면으로 두면 됩니다.",
          ],
          "모델 문서에 적힌 문구가 회사 사이 안전 정책 논쟁의 대상이 됐습니다. 행동강령은 초안·협의용이고, Claude가 실제로 그렇게 훈련되는지는 Anthropic 문서를 따로 열기 전에는 미확정입니다.",
          ["모델복지", "Microsoft AI", "안전"],
          [MAI, REU2],
        ),
        A("extras", 9,
          "🆕 그 밖의 신기능·신제품",
          [
            "브라우저 조수는 모델 선택권과 보존 정책이 본문입니다.",
            "광고 대화는 라벨이 붙은 별도 창이라고 적었습니다.",
            "긴 과제는 중간 상태를 대화 밖에 두는 쪽이 병목을 줄입니다.",
          ],
          [
            "오늘의 작은 출시들은 에이전트에 새 권한을 주되 스위치는 사람 쪽에 남기는 쪽에 가깝습니다. 브라우저 탭도 후원 대화의 라벨도 사용자가 연 뒤에 움직입니다.",
            "살 계획이 있는 하드웨어 호가는 마켓 가격과 제조사 정가를 나눠 보면 됩니다. 이 호에서 독자적으로 확인하지 못한 가격표는 숫자 칸에 넣지 않았습니다.",
          ],
          "오늘의 작은 출시들은 에이전트에 새 권한을 주되 스위치는 사람 쪽에 남깁니다. 확인하지 못한 호가는 숫자 칸에 올리지 않는 편이 안전합니다.",
          ["에이전트", "브라우저", "검수"],
          [OA, AN_DOC],
        ),
    ],
    "mood": {
        "shift": "채팅 문장 대신 타입 있는 판단, Cowork 탭 대신 한 화면으로 기본값이 움직입니다.",
        "grow": "값싼 판정기와 서브에이전트 정리 로그가 같은 날의 성장 축입니다.",
        "caution": "회사 자체 비교표와 ‘환각 불가’ 문장, 141시간의 ‘가장 멀리’는 자기 테스트 기준입니다.",
        "heat": "광고 대화와 모델 복지 논쟁이 무료 창·정책 문서 쪽으로 과열됩니다.",
    },
    "tips": [
        TIP("분류·라우팅은 값싼 판단 모델로 먼저 잽니다",
            "선택지가 고정된 단계는 긴 글을 만들 필요가 없습니다. Jev처럼 출력 구조가 막힌 모델이 $0.042/1M이면 그 구간만 바꿔 보면 됩니다.",
            "TypeSafe AI"),
        TIP("긴 작업은 중간 결과를 대화 밖에 둡니다",
            "141시간 로그가 상자 하나에서 멈추는 것은 모델 점수가 아니라 체크포인트 부재입니다. 산출물을 저장소에 쓰면 됩니다.",
            "운영"),
        TIP("에이전트가 지운 코드는 저장소 밖에서 확인합니다",
            "34.4% 삭제는 줄 수로 성과를 말합니다. 머지 전에 diff를 사람 큐에 올리면 됩니다.",
            "Nous Research"),
        TIP("서브에이전트는 개수를 올릴 때마다 효과를 기록합니다",
            "1,393개를 규칙으로 읽지 않습니다. 개수를 두 배로 늘려 품질이 안 바뀌면 그 구간에서 멈추면 됩니다.",
            "운영"),
        TIP("ChatGPT 무료 창이 광고에서 시작됐는지 봅니다",
            "Sponsored Agents는 라벨이 붙은 별도 대화입니다. 독립 답변과 한 화면에 있어도 로그는 나눠 적으면 됩니다.",
            "OpenAI"),
        TIP("브라우저 AI는 기본값과 모델 선택 화면을 먼저 엽니다",
            "Smart Window는 모델이 여럿입니다. 보존 정책과 기본 모델을 확인한 뒤에 사내 기본값으로 둘지 정하면 됩니다.",
            "Mozilla"),
    ],
    "method": METHOD,
}

# dump() writes to /workspace/content/issues — also write into the Next app tree.
from _editorial import ROOT
dump(issue)
nxt = Path(__file__).resolve().parents[1] / "content" / "issues" / "2026-09-17.json"
nxt.write_text((ROOT / "2026-09-17.json").read_text(encoding="utf-8"), encoding="utf-8")
print("copied", nxt)
