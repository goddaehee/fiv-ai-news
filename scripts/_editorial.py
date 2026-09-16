"""Shared helpers for issue JSON. Editorial Korean, original wording, public facts only."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/workspace/content/issues")
METHOD = (
    "수치는 각 회사의 발표 화면과 공식 문서, 주요 매체 보도에서 가져왔습니다. "
    "자체 측정 벤치마크와 개인 사용량 화면의 값은 본문에 그 사실을 함께 적었으며, "
    "이 리포트는 외부 독립 검증 전입니다."
)


def S(handle: str, url: str, kind: str = "talk") -> dict:
    return {"handle": handle, "url": url, "kind": kind}


def B(id: str, headline: str, summary: str) -> dict:
    return {"id": id, "headline": headline, "summary": summary}


def K(val: str, lab: str, sub: str) -> dict:
    return {"val": val, "lab": lab, "sub": sub}


def TL(t: str, d: str) -> dict:
    return {"t": t, "d": d}


def TIP(title: str, body: str, via: str = "운영") -> dict:
    return {"title": title, "body": body, "via": via}


def A(
    id: str,
    n: int,
    title: str,
    bullets: list[str],
    body: list[str] | str,
    takeaway: str,
    tags: list[str],
    sources: list[dict],
    extra: str | None = None,
) -> dict:
    out = {
        "id": id,
        "title": f"{n}. {title}",
        "bullets": bullets,
        "body": body if isinstance(body, list) else [body],
        "takeaway": takeaway,
        "tags": tags,
        "sources": sources,
    }
    if extra:
        out["extra"] = extra
    return out


def dump(issue: dict) -> None:
    path = ROOT / f"{issue['date']}.json"
    path.write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    nsrc = sum(len(a.get("sources", [])) for a in issue["analysis"])
    print(
        f"wrote {path.name} brief={len(issue['briefing'])} analysis={len(issue['analysis'])} "
        f"keynums={len(issue['keynums'])} tips={len(issue['tips'])} sources={nsrc} readMin={issue['readMin']}"
    )


# Official / public handles used across issues (not original-site tweet IDs).
OA = S("@OpenAI", "https://x.com/OpenAI", "talk")
OA_DOC = S("OpenAI", "https://openai.com", "doc")
AN = S("@AnthropicAI", "https://x.com/AnthropicAI", "talk")
AN_DOC = S("Anthropic", "https://www.anthropic.com", "doc")
DS = S("@deepseek_ai", "https://x.com/deepseek_ai", "talk")
DS_DOC = S("DeepSeek", "https://www.deepseek.com", "doc")
NV = S("@nvidia", "https://x.com/nvidia", "talk")
NV_DOC = S("NVIDIA", "https://www.nvidia.com", "doc")
GD = S("@GoogleDeepMind", "https://x.com/GoogleDeepMind", "talk")
MS = S("@MicrosoftAI", "https://x.com/MicrosoftAI", "talk")
HF = S("@huggingface", "https://x.com/huggingface", "talk")
HF_DOC = S("Hugging Face", "https://huggingface.co", "doc")
REU = S("Reuters", "https://www.reuters.com/", "doc")
BI = S("Business Insider", "https://www.businessinsider.com/", "doc")
AA = S("Artificial Analysis", "https://artificialanalysis.ai/", "doc")
META = S("@MetaAI", "https://x.com/MetaAI", "talk")
AMD = S("@AMD", "https://x.com/AMD", "talk")
COG = S("@cognition_labs", "https://x.com/cognition_labs", "talk")
ARC = S("@arcprize", "https://x.com/arcprize", "talk")
MISTRAL = S("@MistralAI", "https://x.com/MistralAI", "talk")
BYTEDANCE = S("@ByteDance", "https://x.com/ByteDance", "talk")
TENCENT = S("@TencentGlobal", "https://x.com/TencentGlobal", "talk")
GOOGLE = S("@Google", "https://x.com/Google", "talk")
SEMI = S("SemiAnalysis", "https://semianalysis.com/", "doc")
INFO = S("The Information", "https://www.theinformation.com/", "doc")
BLOOM = S("Bloomberg", "https://www.bloomberg.com/", "doc")
