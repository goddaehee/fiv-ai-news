#!/usr/bin/env python3
"""Collect public AI/tech items from RSS, HN, and official blogs.

No original-site scrape. Output is a dated JSON snapshot the drafter consumes.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; fiv-ai-news/1.1; +https://github.com/goddaehee/fiv-ai-news)"
CTX = ssl.create_default_context()

FEEDS = [
    ("OpenAI News", "https://openai.com/news/rss.xml", "doc"),
    (
        "Anthropic News",
        "https://raw.githubusercontent.com/alan-turing-institute/ai-rss-feeds/refs/heads/main/feeds/anthropic-news.xml",
        "doc",
    ),
    (
        "Anthropic GNews",
        "https://news.google.com/rss/search?q=Anthropic+when:2d&hl=en-US&gl=US&ceid=US:en",
        "news",
    ),
    ("Google Blog", "https://blog.google/rss/", "doc"),
    ("DeepMind", "https://deepmind.google/blog/feed/basic/", "doc"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", "doc"),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/", "doc"),
    ("Meta News", "https://about.fb.com/news/feed/", "doc"),
    ("Meta Eng", "https://engineering.fb.com/feed/", "doc"),
    ("Azure Blog", "https://azure.microsoft.com/en-us/blog/feed/", "doc"),
    ("MS Research", "https://www.microsoft.com/en-us/research/feed/", "doc"),
    # P19: kind 교정 — "doc"은 공식 블로그·문서(회사 1차 발표)만. 언론 매체와
    # Google News 중계 피드는 "news". 전 피드가 doc이던 시절에는 모든 출처에
    # "1차 출처 포함" 배지가 붙는 오표시가 됐다 (4차 패널 평가 Codex P0).
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "news"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "news"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", "news"),
    # P16: 보안 톱뉴스(제로데이·대규모 취약점) 수집 경로. php2shell 같은
    # 사건은 AI 전문 매체보다 보안 매체가 먼저·깊게 다루는데 피드가 없어
    # 통째로 누락됐다 (2026-10-23 원본 톱 php2shell 미수집 실측).
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "news"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "news"),
    ("HN AI", "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini", "talk"),
    (
        "Google News AI",
        "https://news.google.com/rss/search?q=artificial+intelligence+OR+LLM+when:1d&hl=en-US&gl=US&ceid=US:en",
        "news",
    ),
]

AI_HINT = re.compile(
    r"\b(ai|llm|gpt|claude|gemini|openai|anthropic|nvidia|model|agent|gpu|"
    r"inference|benchmark|safety|coding)\b",
    re.I,
)
# P16: 보안 피드 전용 통과 힌트. 보안 매체는 AI와 무관한 기사도 많아서
# AI_HINT만으로는 부족하고, 반대로 보안 키워드만으로 다 받으면 노이즈가 된다.
# 보안 피드는 AI_HINT 또는 SECURITY_HINT 중 하나라도 걸리면 수집한다.
SECURITY_HINT = re.compile(
    r"vulnerab|zero[- ]?day|exploit|malware|ransomware|data breach|"
    r"\bcve-\d|phishing|backdoor|botnet|hackers?\b|breached|patch(ed)?\s+(tuesday|flaw)",
    re.I,
)
SECURITY_SOURCES = {"The Hacker News", "BleepingComputer"}
TAG = re.compile(r"<[^>]+>")

# P5: 피드별 수집 상한. Google News AI는 limit=40이 수집의 60%를 폐기하므로 100으로 상향.
FEED_LIMITS = {
    "Google News AI": 100,
}

# P5: 신선도 필터 — 48시간 초과 기사는 제외 (데일리 다이제스트 기준)
FRESHNESS_HOURS = 48


def fetch(url: str, timeout: int = 22) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, application/json, */*"},
    )
    last: Exception | None = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as res:
                return res.read()
        except urllib.error.HTTPError as e:
            print(f"    HTTP {e.code} {url[:88]}")
            return None
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ValueError, ConnectionError) as e:
            last = e
            time.sleep(0.5)
    print(f"    fail {type(last).__name__ if last else 'error'} {url[:88]}")
    return None


def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    raw = "".join(el.itertext()) if list(el) else (el.text or "")
    return unescape(TAG.sub(" ", raw)).replace("\xa0", " ")
    # collapse later


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_date(el: ET.Element | None) -> str | None:
    raw = text_of(el)
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).isoformat(timespec="minutes")
    except (TypeError, ValueError, OverflowError):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        return f"{m.group(1)}T00:00+09:00" if m else raw[:32]


def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child(node: ET.Element, *names: str) -> ET.Element | None:
    want = {n.lower() for n in names}
    for c in list(node):
        if localname(c.tag) in want:
            return c
    return None


def parse_feed(xml: bytes, source: str, kind: str, limit: int = 40) -> list[dict]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    items = []
    nodes = [n for n in root.iter() if localname(n.tag) in {"item", "entry"}]
    for node in nodes:
        title = collapse(text_of(child(node, "title")))
        if not title:
            continue
        link_el = child(node, "link")
        link = ""
        if link_el is not None:
            link = (link_el.get("href") or text_of(link_el)).strip()
        if not link:
            for c in node:
                if localname(c.tag) == "link" and c.get("rel") in (None, "alternate"):
                    link = (c.get("href") or text_of(c)).strip()
                    if link:
                        break
        summary = collapse(text_of(child(node, "description", "summary", "content")))[:420]
        published = parse_date(child(node, "pubdate", "published", "updated", "date", "created"))
        # P5: Google News <source url="실발행처URL"> 파싱 — 불투명 리다이렉트 URL 대신
        # 실제 발행처 도메인을 origin_url에 저장 (RSS 내부 데이터라 No-scrape 제약 위반 아님)
        # P19: <source> 요소 텍스트(발행처 이름, 예: "Reuters")도 함께 저장한다.
        # 지금까지는 url 속성만 읽고 이름을 버려서, 발행본 출처 라벨이 피드명
        # ("Anthropic GNews")으로 남았다. 이름은 draft의 출처 라벨 조립에 쓴다.
        origin_url = None
        publisher = None
        source_el = child(node, "source")
        if source_el is not None:
            origin_url = (source_el.get("url") or "").strip() or None
            publisher = collapse(text_of(source_el)) or None
        blob = f"{title} {summary}"
        if source.startswith("Google News") or "GNews" in source or source.startswith("HN") or AI_HINT.search(blob):
            keep = True
        elif source in SECURITY_SOURCES:
            # P16: 보안 피드는 AI 힌트 또는 보안 힌트가 있을 때만
            keep = bool(AI_HINT.search(blob) or SECURITY_HINT.search(blob))
        else:
            keep = bool(AI_HINT.search(blob))
        if keep:
            item = {
                "source": source,
                "kind": kind,
                "title": title,
                "url": link,
                "summary": summary,
                "published": published,
            }
            if origin_url:
                item["origin_url"] = origin_url
            if publisher:
                item["publisher"] = publisher
            items.append(item)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# P31: Google News 중계 링크 → 기사 직행 URL 해소.
# 중계 링크(news.google.com/rss/articles/…)는 브라우저에서 간이 페이지를
# 거쳐 원문으로 넘어가는 구조라, 발행본 출처가 "원문으로 바로 가는 링크"가
# 아니었다 (6차 패널 평가 공통 지적). 수집 단계에서 링크의 최종 목적지만
# 확인해 item["url"]을 직행 URL로 교체한다 — 원문 본문을 긁는 것이 아니라
# RSS가 준 링크의 목적지 확인이다. 실패하면 중계 링크를 그대로 둔다
# (best-effort — 해소 실패가 수집을 막지 않는다). 원본 중계 링크는
# relay_url에 남긴다.
# ---------------------------------------------------------------------------

_GNEWS_DECODE_ENDPOINT = "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je"
_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _fetch_text(url: str, timeout: int = 12, data: bytes | None = None) -> str | None:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": _BROWSER_UA,
                 "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as res:
            return res.read().decode("utf-8", "replace")
    except Exception:
        return None


def decode_gnews_response(resp: str | None) -> str | None:
    """batchexecute 응답에서 기사 URL만 뽑는다. 형식이 어긋나면 None."""
    if not resp:
        return None
    try:
        body = resp.split("\n", 1)[1] if resp.startswith(")]}'") else resp
        outer = json.loads(body)
        decoded = json.loads(outer[0][2])
        url = decoded[1]
        return url if isinstance(url, str) and url.startswith("http") else None
    except Exception:
        return None


def resolve_relay_url(url: str, fetch_text=_fetch_text) -> str | None:
    """중계 링크 1건 해소. 페이지의 data-n-a-* 서명을 읽어 Google News의
    디코드 호출로 실제 기사 URL을 얻는다. 어느 단계든 실패하면 None."""
    page = fetch_text(url)
    if not page:
        return None
    m_id = re.search(r'data-n-a-id="([^"]+)"', page)
    m_ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    m_sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    if not (m_id and m_ts and m_sg):
        return None
    try:
        ts = int(m_ts.group(1))
    except ValueError:
        return None
    inner = ["garturlreq",
             [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 180,
               None, None, None, None, None, 0, None, None,
               [1608992183, 723558691]],
              "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             m_id.group(1), ts, m_sg.group(1)]
    payload = [["Fbv4je", json.dumps(inner), None, "generic"]]
    body = urllib.parse.urlencode(
        {"f.req": json.dumps([payload])}).encode("utf-8")
    resp = fetch_text(_GNEWS_DECODE_ENDPOINT, data=body)
    return decode_gnews_response(resp)


def _is_relay(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        return (urlparse(url or "").hostname or "") == "news.google.com"
    except Exception:
        return False


def resolve_gnews_links(items: list[dict], resolver=resolve_relay_url,
                        max_workers: int = 8) -> int:
    """items의 중계 링크를 직행 URL로 교체하고, 해소로 생긴 URL 중복을
    제거한다. 반환: 교체 건수. resolver 주입은 테스트용."""
    targets = [it for it in items if _is_relay(str(it.get("url") or ""))]
    if not targets:
        return 0
    from concurrent.futures import ThreadPoolExecutor

    def _one(it: dict) -> None:
        try:
            direct = resolver(str(it.get("url") or ""))
        except Exception:
            direct = None
        if direct:
            it["relay_url"] = it["url"]
            it["url"] = direct

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(_one, targets))
    # 병렬 1차에서 실패한 건은 동시 요청 throttling인 경우가 많아(실측:
    # 직렬 재시도 시 ~3초에 성공), 워커를 줄여 한 번만 더 시도한다.
    retry = [it for it in targets if not it.get("relay_url")]
    if retry:
        with ThreadPoolExecutor(max_workers=3) as ex:
            list(ex.map(_one, retry))
    resolved = sum(1 for it in targets if it.get("relay_url"))
    # 해소 결과 직행 URL이 직접 피드 아이템과 같아지면 같은 기사이므로
    # 먼저 수집된 쪽만 남긴다 (스냅샷 순서는 직접 피드가 앞이다).
    seen: set[str] = set()
    kept: list[dict] = []
    for it in items:
        u = str(it.get("url") or "")
        if u and u in seen:
            continue
        seen.add(u)
        kept.append(it)
    items[:] = kept
    return resolved


def hn_algolia(hours: int = 36) -> list[dict]:
    since = int(time.time()) - hours * 3600
    url = (
        "https://hn.algolia.com/api/v1/search_by_date?tags=story"
        f"&numericFilters=created_at_i>{since}&hitsPerPage=40"
        "&query=AI&hitsPerPage=40"
    )
    raw = fetch(url)
    if not raw:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return []
    out = []
    for h in data.get("hits") or []:
        title = h.get("title") or ""
        if not title:
            continue
        out.append(
            {
                "source": "Hacker News",
                "kind": "talk",
                "title": title,
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                "summary": (h.get("story_text") or "")[:420],
                "published": datetime.fromtimestamp(h.get("created_at_i") or 0, tz=timezone.utc).astimezone(KST).isoformat(timespec="minutes"),
                "points": h.get("points"),
            }
        )
    return out


def collect() -> dict:
    items: list[dict] = []
    errors: list[str] = []
    for name, url, kind in FEEDS:
        raw = fetch(url)
        if not raw:
            errors.append(name)
            continue
        got = parse_feed(raw, name, kind, limit=FEED_LIMITS.get(name, 40))
        items.extend(got)
        print(f"  {name:18} {len(got):3d}")
    hn = hn_algolia()
    items.extend(hn)
    print(f"  {'HN Algolia':18} {len(hn):3d}")
    seen = set()
    uniq = []
    for it in items:
        key = (it["title"].lower(), it.get("url") or "")
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    now = datetime.now(KST)
    # P5: 48h 신선도 필터 — 너무 오래된 기사는 제외 (날짜 파싱 불가 시 유지)
    cutoff = now - timedelta(hours=FRESHNESS_HOURS)
    fresh: list[dict] = []
    stale = 0
    for it in uniq:
        pub = it.get("published")
        dt = None
        if pub:
            try:
                dt = datetime.fromisoformat(pub)
            except ValueError:
                dt = None
        if dt is None:
            fresh.append(it)
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        if dt >= cutoff:
            fresh.append(it)
        else:
            stale += 1
    if stale:
        print(f"  stale(48h+) dropped: {stale}")
    uniq = fresh
    # P31: Google News 중계 링크를 기사 직행 URL로 해소 (best-effort).
    # 신선도 필터를 통과한 아이템만 대상이라 호출 수가 제한된다.
    n_resolved = resolve_gnews_links(uniq)
    if n_resolved:
        print(f"  gnews direct links resolved: {n_resolved}")
    # P5: 도메인 분포 로그 — origin_url 우선으로 유효 도메인 확인
    from urllib.parse import urlparse
    from collections import Counter

    def _dom(u: str) -> str:
        try:
            h = (urlparse(u or "").hostname or "").lower()
            return h[4:] if h.startswith("www.") else h
        except Exception:
            return ""

    dom_counts = Counter(_dom(it.get("origin_url") or it.get("url")) for it in uniq)
    top = dict(dom_counts.most_common(8))
    print(f"  domains: {top}")
    return {
        "collected_at": now.isoformat(timespec="minutes"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A"),
        "count": len(uniq),
        "failed_feeds": errors,
        "items": uniq,
    }


def default_out(date: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    # workspace or next/ checkout
    for cand in (root / "content" / "pipeline", root / "next" / "content" / "pipeline"):
        if cand.parent.exists():
            cand.mkdir(parents=True, exist_ok=True)
            return cand / f"{date}.collected.json"
    path = Path("content/pipeline")
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}.collected.json"


def main() -> None:
    p = argparse.ArgumentParser(description="Collect public AI/tech RSS into a dated snapshot")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    print("collecting feeds…")
    snap = collect()
    out = args.out or default_out(snap["date"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} items={snap['count']} failed={snap['failed_feeds']}")


if __name__ == "__main__":
    main()
