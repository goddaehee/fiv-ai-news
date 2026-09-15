# 콘텐츠 소스

호·레포·FAQ는 TypeScript가 아니라 **파일 하나 = 글 하나**입니다.
Next.js로 옮길 때도 이 폴더를 그대로 가져가면 됩니다.

```text
content/
  issues/YYYY-MM-DD.json   하루 1호
  repos/{slug}.json        레포 딥다이브
  faq.json
  schema/issue.schema.json
```

## 규칙

- 스키마는 `schema/issue.schema.json`을 따른다.
- 분석 본문의 `sources`는 계정 홈이 아니라 **특정 문서·게시물 URL**을 넣는다. `kind: "doc"`이 1차 출처다.
- 브리핑 항목 중 분석이 없는 id는 그날 호에서 브리핑만 나간다. 억지로 본문을 채우지 않는다.
- 평일만 발행한다. 주말·공휴일 파일은 만들지 않는다.

## Next.js에서 읽는 법

```ts
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const dir = path.join(process.cwd(), "content/issues");
const files = (await readdir(dir)).filter((f) => f.endsWith(".json"));
```

`generateStaticParams()`에 파일 이름을 그대로 쓰면 `/news/2026-09-15`가 된다.
