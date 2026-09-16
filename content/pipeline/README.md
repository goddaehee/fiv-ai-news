# 콘텐츠 파이프라인

매일 아침 호는 RSS·HN에서 **공개 소스만** 모은 뒤, 한국어로 다시 써서 `content/issues/YYYY-MM-DD.json`이 됩니다. 원 매체 HTML을 긁지 않습니다.

```text
23:00 KST  collect.py   RSS + HN 스냅샷
05:30 KST  draft.py     편집 초안 (XAI_API_KEY가 있으면 LLM, 없으면 스켈레톤)
         validate.py  스키마·톤 검사
평일만    주말 파일은 만들지 않음
```

## 로컬

```bash
python3 scripts/pipeline/run.py --collect-only
python3 scripts/pipeline/run.py --llm          # 키 필요
python3 scripts/pipeline/validate.py content/issues/*.json
```

환경변수:

| 키 | 용도 |
|---|---|
| `XAI_API_KEY` 또는 `GROK_API_KEY` | xAI로 한국어 초안 |
| `XAI_MODEL` | 기본 `grok-4` |
| `OPENAI_API_KEY` | OpenAI 폴백 |

키가 없으면 토픽 묶음 스켈레톤만 씁니다. 시사점의 `하십시오`는 검증이 막습니다.

## GitHub Actions

`.github/workflows/daily-issue.yml` — 평일 05:30 KST (`20:30 UTC` 전날). 저장소 Secret에 `XAI_API_KEY`를 넣으면 초안 PR이 열립니다. 없으면 수집 JSON만 아티팩트로 남습니다.

## 발행

1. PR 본문을 읽고 수치·출처 URL을 공식 페이지와 맞춘다
2. 머지하면 Vercel이 `/news/YYYY-MM-DD`를 다시 빌드한다
3. 메일 발송은 이후 Resend
