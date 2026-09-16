import Link from "next/link";
import type { Repo } from "@/data/types";
import { SaveRepoButton } from "./SaveRepoButton";

export function RepoDeepDive({ repo }: { repo: Repo }) {
  return (
    <article className="dd-wrap">
      <p className="kicker">
        TRENDSHIFT #{repo.trendRank} 딥다이브 · {repo.updated} 분석
        <SaveRepoButton slug={repo.slug} />
      </p>
      <h1>
        {repo.name} 딥다이브 — {repo.oneLiner}
      </h1>
      <p className="dd-sub">
        {repo.analogy} <strong>★ {repo.stars}</strong> · {repo.repo} · {repo.license} · {repo.lang}
      </p>

      <nav className="toc" aria-label="목차">
        <div className="title">목차</div>
        <ol>
          <li>
            <a href="#s1">프로젝트 한줄 요약</a>
          </li>
          <li>
            <a href="#s2">왜 주목받는가</a>
          </li>
          <li>
            <a href="#s3">기술 스택</a>
          </li>
          <li>
            <a href="#s4">아키텍처</a>
          </li>
          <li>
            <a href="#s5">디렉터리 구조</a>
          </li>
          <li>
            <a href="#s6">학습 포인트</a>
          </li>
          <li>
            <a href="#s7">요구사항</a>
          </li>
          <li>
            <a href="#s8">실습 과제</a>
          </li>
          <li>
            <a href="#s9">키워드</a>
          </li>
          <li>
            <a href="#s10">참고 링크</a>
          </li>
        </ol>
      </nav>

      <h2 id="s1">
        <span className="num">1</span>프로젝트 한줄 요약
      </h2>
      <p className="h2-sub">{repo.name}가 정확히 무엇을 하는 도구인가</p>
      <p>{repo.oneLiner}</p>
      <div className="hero-analogy">
        <div className="tag">한 컷 비유</div>
        <h3 style={{ margin: "8px 0 10px", fontSize: 18 }}>{repo.analogyTitle}</h3>
        <p>{repo.analogy}</p>
      </div>

      <h2 id="s2">
        <span className="num">2</span>왜 주목받는가
      </h2>
      <p className="h2-sub">트렌딩 이유와 경쟁 도구 대비 강점</p>
      <div className="callout pain">
        <div className="label">기존 방식의 불편함</div>
        <p>{repo.pain}</p>
      </div>
      <div className="callout good">
        <div className="label">{repo.name}의 해법</div>
        <p>{repo.fix}</p>
      </div>
      <p>{repo.why}</p>
      <table>
        <thead>
          <tr>
            <th>비교 대상</th>
            <th>포인트</th>
          </tr>
        </thead>
        <tbody>
          {repo.compare.map((c) => (
            <tr key={c.vs}>
              <td>{c.vs}</td>
              <td>{c.point}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="s3">
        <span className="num">3</span>기술 스택
      </h2>
      <p className="h2-sub">언어 구성 · 런타임 · 인프라</p>
      {repo.languages.map((l) => (
        <div className="lang-row" key={l.name}>
          <span>{l.name}</span>
          <div className="lang-bar">
            <span style={{ width: `${l.bar}%` }} />
          </div>
          <span>
            {l.pct} · {l.note}
          </span>
        </div>
      ))}
      <table>
        <thead>
          <tr>
            <th>기술</th>
            <th>역할</th>
            <th>상세</th>
          </tr>
        </thead>
        <tbody>
          {repo.stack.map((s) => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td>{s.role}</td>
              <td>{s.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="s4">
        <span className="num">4</span>아키텍처
      </h2>
      <p className="h2-sub">실행 경로와 핵심 패턴</p>
      <pre className="ascii">{repo.architecture}</pre>
      {repo.patterns.map((p) => (
        <div className="callout" key={p.name}>
          <div className="label">{p.name}</div>
          <p>{p.body}</p>
        </div>
      ))}

      <h2 id="s5">
        <span className="num">5</span>디렉터리 구조
      </h2>
      <pre className="ascii">{repo.tree}</pre>

      <h2 id="s6">
        <span className="num">6</span>학습 포인트
      </h2>
      {repo.learn.map((l) => (
        <p key={l.title}>
          <strong>{l.title}.</strong> {l.body}
        </p>
      ))}

      <h2 id="s7">
        <span className="num">7</span>요구사항
      </h2>
      <table>
        <thead>
          <tr>
            <th>항목</th>
            <th>최소</th>
            <th>권장</th>
          </tr>
        </thead>
        <tbody>
          {repo.requirements.map((r) => (
            <tr key={r.item}>
              <td>{r.item}</td>
              <td>{r.min}</td>
              <td>{r.rec}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="s8">
        <span className="num">8</span>실습 과제
      </h2>
      {repo.exercises.map((ex, i) => (
        <p key={ex.title}>
          <strong>
            {i + 1}. {ex.title}
          </strong>
          <br />
          {ex.body}
        </p>
      ))}

      <h2 id="s9">
        <span className="num">9</span>키워드 사전
      </h2>
      <table>
        <tbody>
          {repo.keywords.map((k) => (
            <tr key={k.word}>
              <td>
                <strong>{k.word}</strong>
              </td>
              <td>{k.meaning}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="s10">
        <span className="num">10</span>참고 링크
      </h2>
      <ul>
        {repo.links.map((l) => (
          <li key={l.href}>
            <a href={l.href} target="_blank" rel="noopener noreferrer">
              {l.label}
            </a>
          </li>
        ))}
      </ul>

      <p style={{ marginTop: 36 }}>
        <Link href="/repos" style={{ color: "var(--color-accent-ink)", fontWeight: 700 }}>
          ← 레포 카탈로그
        </Link>
      </p>
    </article>
  );
}
