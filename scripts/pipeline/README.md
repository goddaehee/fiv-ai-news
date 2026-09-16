# 콘텐츠 파이프라인

매일 아침 호는 RSS·HN에서 **공개 소스만** 모은 뒤, 한국어로 다시 써서 `content/issues/YYYY-MM-DD.json`이 됩니다. 원 매체 HTML을 긁지 않습니다.

```text
23:00 KST  collect.py   RSS + HN 스냅샷
05:30 KST  draft.py     편집 초안 (GLM/xAI/OpenAI 키가 있으면 LLM, 없으면 스켈레톤)
         validate.py  스키마·톤 검사
평일만    주말 파일은 만들지 않음
```

## 로컬

```bash
python3 scripts/pipeline/run.py --collect-only
python3 scripts/pipeline/run.py --llm --provider glm
python3 scripts/pipeline/validate.py content/issues/*.json
```

환경변수:

| 키 | 용도 |
|---|---|
| `GLM_API_KEY` 또는 `ZHIPU_API_KEY` | 지푸 GLM으로 한국어 초안 |
| `GLM_MODEL` | 기본 `glm-4.6` |
| `GLM_BASE_URL` | 기본 `https://open.bigmodel.cn/api/paas/v4`. 해외면 `https://api.z.ai/api/paas/v4` |
| `LLM_PROVIDER` | `glm` / `xai` / `openai` — 키가 여러 개일 때 강제 |
| `XAI_API_KEY` 또는 `GROK_API_KEY` | xAI |
| `OPENAI_API_KEY` | OpenAI 폴백 |

키가 없으면 토픽 묶음 스켈레톤만 씁니다. 시사점의 `하십시오`는 검증이 막습니다.

GLM 예:

```bash
export GLM_API_KEY=...
export LLM_PROVIDER=glm
# 해외 엔드포인트면
# export GLM_BASE_URL=https://api.z.ai/api/paas/v4
python3 scripts/pipeline/run.py --llm --provider glm
```

## GitHub Actions

`.github/workflows/daily-issue.yml` — 평일 05:30 KST. Secret에 `GLM_API_KEY`(또는 xAI/OpenAI)를 넣으면 초안 PR이 열립니다. 키가 여러 개면 `LLM_PROVIDER=glm`도 같이 넣으면 됩니다.

## 발행

1. PR 본문을 읽고 수치·출처 URL을 공식 페이지와 맞춘다
2. 머지하면 Vercel이 `/news/YYYY-MM-DD`를 다시 빌드한다
3. 메일 발송은 이후 Resend
