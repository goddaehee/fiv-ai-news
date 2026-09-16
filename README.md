# 5분 AI 뉴스 (클론코딩)

매일 아침 AI·테크 흐름을 한국어 5분 브리핑과 전체 분석으로 정리하는 뉴스 사이트입니다.

이 저장소는 [fiv.co.kr](https://fiv.co.kr)의 **독립 재창작**입니다. 원 매체와 무관하며, 원문 145호를 스크랩하지 않습니다. 레이아웃·톤·정보 구조만 맞추고 본문은 자체 재구성입니다.

## 스택

- Next.js 15 App Router
- 정적 JSON 콘텐츠 (`content/issues`, `content/repos`)
- pnpm
- Vercel 배포

## 로컬

```bash
pnpm install
pnpm dev
```

## Vercel 연결

GitHub 레포: [goddaehee/fiv-ai-news](https://github.com/goddaehee/fiv-ai-news)

Vercel 대시보드에서 **Add New Project → Import Git Repository → `goddaehee/fiv-ai-news`**.

- Framework Preset: Next.js
- Install Command: `pnpm install`
- Build Command: `pnpm build`
- 팀: goddaehee's projects (hobby)

GitHub App이 이 레포를 아직 못 보면, Vercel → Settings → Git → Connect GitHub 후 다시 Import 하면 됩니다.

## 콘텐츠 파이프라인 (운영 서버·GitHub Actions)

원문 사이트를 긁지 않습니다. 공식 블로그 RSS·HN·Google News만 모은 뒤 한국어로 다시 씁니다.

```bash
python3 scripts/pipeline/run.py --collect-only
python3 scripts/pipeline/validate.py content/issues/*.json
```

1. 평일 05:30 KST — GitHub Action이 수집 후, Secret `GLM_API_KEY`(또는 xAI/OpenAI)가 있으면 초안 PR
2. 편집자가 수치·출처를 공식 페이지와 맞춤
3. 머지 후 Vercel이 `/news/YYYY-MM-DD` 재빌드
4. 메일 발송은 이후 Resend

키가 없으면 수집 JSON만 아티팩트로 남습니다. GLM을 쓰려면 레포 Secrets에 `GLM_API_KEY`와 `LLM_PROVIDER=glm`을 넣으면 됩니다. 모델 기본값은 `glm-5.3`, 엔드포인트는 `https://api.z.ai/api/paas/v4`입니다. 중국 리전이면 `GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`.

글·레포·검색은 JSON 파일이라 **DB는 없습니다.** 구독은 브라우저 localStorage입니다. 메일 명단·조회수·여러 기기 저장을 붙일 때만 DB가 필요합니다.

## 하지 않는 것

- 원 운영자 이메일·광고·관리자 CMS
- 원문 145호·691개 딥다이브 전문 복제 (카탈로그 목록 689개 + 한국어 딥다이브 20편)
