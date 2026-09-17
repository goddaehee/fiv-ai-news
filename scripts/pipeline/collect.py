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
        "https://news.google.com/rss/search?q=site:anthropic.com+when:2d&hl=en-US&gl=US&ceid=US:en",
        "doc",
    ),
    ("Google Blog", "https://blog.google/rss/", "doc"),
    ("DeepMind", "https://deepmind.google/blog/feed/basic/", "doc"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", "doc"),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/", "doc"),
    ("Meta News", "https://about.fb.com/news/feed/", "doc"),
    ("Meta Eng", "https://engineering.fb.com/feed/", "doc"),
    ("Azure Blog", "https://azure.microsoft.com/en-us/blog/feed/", "doc"),
    ("MS Research", "https://www.microsoft.com/en-us/research/feed/", "doc"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "doc"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "doc"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", "doc"),
    ("HN AI", "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini", "talk"),
    (
        "Google News AI",
        "https://news.google.com/rss/search?q=artificial+intelligence+OR+LLM+when:1d&hl=en-US&gl=US&ceid=US:en",
        "doc",
    ),
]

AI_HINT = re.compile(
    r"\b(ai|llm|gpt|claude|gemini|openai|anthropic|nvidia|model|agent|gpu|"
    r"inference|benchmark|safety|coding)\b",
    re.I,
)
TAG = re.compile(r"<[^>]+>")


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
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ValueError) as e:
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
        blob = f"{title} {summary}"
        if source.startswith("Google News") or source.startswith("HN") or AI_HINT.search(blob):
            items.append(
                {
                    "source": source,
                    "kind": kind,
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "published": published,
                }
            )
        if len(items) >= limit:
            break
    return items


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
        got = parse_feed(raw, name, kind)
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
