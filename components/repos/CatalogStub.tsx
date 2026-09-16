import Link from "next/link";
import { githubSearch } from "@/data/catalog";
import { REPOS } from "@/data/repos";

export function CatalogStub({
  name,
  category,
  subcategory,
}: {
  name: string;
  category: string;
  subcategory: string;
}) {
  return (
    <article className="dd-wrap">
      <p className="kicker">유행레포 카탈로그 · {category}</p>
      <h1>{name}</h1>
      <p className="dd-sub">{subcategory}</p>
      <p>
        이 클론에는 같은 틀의 전체 한국어 딥다이브가 <strong>{REPOS.length}편</strong> 있습니다. 이 이름은 원본
        카탈로그 분류에 있던 항목이며, 여기서는 목록 탐색용으로 남겨 두었습니다.
      </p>
      <p>
        <a className="site-button" href={githubSearch(name)} target="_blank" rel="noopener noreferrer">
          GitHub에서 찾기 ↗
        </a>
      </p>
      <p style={{ marginTop: 36 }}>
        <Link href="/repos" style={{ color: "var(--color-accent-ink)", fontWeight: 700 }}>
          ← 레포 카탈로그
        </Link>
      </p>
    </article>
  );
}
