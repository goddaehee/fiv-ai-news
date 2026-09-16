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

## 콘텐츠 파이프라인 (운영 서버 크론)

1. 23:00 KST — X·공식 블로그 수집
2. 05:30 KST — 교차검증 후 이슈 JSON 초안 → PR
3. 머지 후 Vercel 재빌드
4. 평일 07:00 — 이메일 발송 (이후 Resend 등)

이 데모의 구독 폼은 브라우저에만 저장되며 메일을 보내지 않습니다.

## 하지 않는 것

- 원 운영자 이메일·광고·관리자 CMS
- 원문 145호·691개 딥다이브 전문 복제 (카탈로그 목록 689개 + 한국어 딥다이브 20편)
