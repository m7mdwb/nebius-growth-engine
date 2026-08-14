"""Engine adapters.

Every engine returns the same shape, so adding one is a single function and the
analysis layer never learns which surface it is reading:

    EngineResult(engine, is_live, answer, citations, error)

Two are live and two are declared seams. A seam is NOT a silent failure — it is
recorded in the database with is_live=0 and rendered as a seam in the dashboard,
because "we did not measure this" and "we measured this and found nothing" are
different findings and must never look alike.

🔑 The distinction that matters most here: SEARCH RESULTS ARE NOT CITATIONS.
An engine may retrieve twenty pages and cite three. Only the cited ones shaped
the answer the buyer reads, so `citations` holds what the answer actually cited,
not everything the search returned.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .config import Config, env


@dataclass
class EngineResult:
    engine: str
    is_live: bool
    answer: str = ""
    citations: list[dict] = field(default_factory=list)   # {url, domain, title}
    error: str | None = None
    note: str | None = None      # why a seam is a seam, shown in the UI


def domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


# ---------------------------------------------------------------------------
# LIVE — Claude with the web_search server tool
# ---------------------------------------------------------------------------

def claude(query: str, cfg: Config) -> EngineResult:
    key = env("ANTHROPIC_API_KEY")
    if not key:
        return EngineResult("claude", False, note="no ANTHROPIC_API_KEY set")

    import anthropic

    model = cfg.engines.get("claude", {}).get("model", "claude-opus-5")
    max_tokens = int(cfg.engines.get("claude", {}).get("max_tokens", 2000))
    client = anthropic.Anthropic(api_key=key)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            # No system prompt on purpose. We are measuring what an ordinary
            # user sees, so steering the assistant would corrupt the reading.
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": query}],
        )
    except Exception as exc:  # noqa: BLE001 - any failure is a recorded miss, not a crash
        return EngineResult("claude", True, error=f"{type(exc).__name__}: {exc}")

    # A long server-tool turn can stop early; resume once rather than reporting
    # a truncated answer as if it were the whole answer.
    if getattr(resp, "stop_reason", None) == "pause_turn":
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
                messages=[
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": resp.content},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            return EngineResult("claude", True, error=f"resume failed: {exc}")

    if getattr(resp, "stop_reason", None) == "refusal":
        return EngineResult("claude", True, error="refused by safety classifier")

    text_parts: list[str] = []
    cites: dict[str, dict] = {}

    for block in resp.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
            # Citations attached to the answer text = what the answer actually
            # leaned on. This is the number that matters, not the search hits.
            for c in (getattr(block, "citations", None) or []):
                url = getattr(c, "url", None)
                if not url:
                    continue
                cites.setdefault(url, {
                    "url": url,
                    "domain": domain_of(url),
                    "title": getattr(c, "title", None) or "",
                })

    return EngineResult("claude", True, answer="\n".join(text_parts).strip(),
                        citations=list(cites.values()))


# ---------------------------------------------------------------------------
# LIVE — Google AI Overviews, via Apify
# ---------------------------------------------------------------------------

# AI Overviews is the generative surface with the most commercial traffic and
# has no public API, which is exactly why capturing it is worth the trouble.
# Scraper output shapes drift, so the parser probes several known key names and
# degrades to a MARKED SEAM rather than inventing an absence.
_AIO_KEYS = ("aiOverview", "ai_overview", "aiOverviews", "generativeAiOverview")
_APIFY_ACTOR = "apify~google-search-scraper"


def ai_overviews(query: str, cfg: Config) -> EngineResult:
    token = env("APIFY_TOKEN")
    if not token:
        return EngineResult("ai_overviews", False,
                            note="no APIFY_TOKEN set — Google AI Overviews not captured")

    from apify_client import ApifyClient

    country = cfg.engines.get("ai_overviews", {}).get("country", "us")
    client = ApifyClient(token)

    try:
        run = client.actor(_APIFY_ACTOR).call(
            run_input={
                "queries": query,
                "resultsPerPage": 10,
                "maxPagesPerQuery": 1,
                "countryCode": country,
                "languageCode": "en",
            },
            timeout_secs=180,
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    except Exception as exc:  # noqa: BLE001
        return EngineResult("ai_overviews", True, error=f"{type(exc).__name__}: {exc}")

    if not items:
        return EngineResult("ai_overviews", True, error="actor returned no items")

    page = items[0]
    aio = next((page[k] for k in _AIO_KEYS if page.get(k)), None)

    if not aio:
        # Two very different things look identical here and must not be merged:
        # Google served no AI Overview for this query, OR the scraper does not
        # expose the field. We cannot tell them apart, so we say so.
        return EngineResult(
            "ai_overviews", False,
            note="no AI Overview field in scraper output — either Google served "
                 "none for this query or the actor does not expose it. "
                 "Not counted as an absence.",
        )

    answer = aio.get("content") or aio.get("text") or aio.get("markdown") or ""
    if isinstance(answer, list):
        answer = "\n".join(str(x) for x in answer)

    cites: dict[str, dict] = {}
    for src in (aio.get("sources") or aio.get("references") or aio.get("links") or []):
        url = src.get("url") if isinstance(src, dict) else str(src)
        if not url:
            continue
        cites.setdefault(url, {
            "url": url,
            "domain": domain_of(url),
            "title": (src.get("title") if isinstance(src, dict) else "") or "",
        })

    return EngineResult("ai_overviews", True, answer=str(answer).strip(),
                        citations=list(cites.values()))


# ---------------------------------------------------------------------------
# SEAMS — declared, not hidden
# ---------------------------------------------------------------------------

def _seam(name: str, why: str):
    def run(query: str, cfg: Config) -> EngineResult:  # noqa: ARG001
        return EngineResult(name, False, note=why)
    return run


chatgpt = _seam(
    "chatgpt",
    "SEAM: no OpenAI key on this account. The adapter is one function with the "
    "same return shape as the live engines — this is a credential gap, not a "
    "design gap.",
)

perplexity = _seam(
    "perplexity",
    "SEAM: no Perplexity key on this account. Same shape as the live engines.",
)


ENGINES = {
    "claude": claude,
    "ai_overviews": ai_overviews,
    "chatgpt": chatgpt,
    "perplexity": perplexity,
}

ENGINE_LABELS = {
    "claude": "Claude",
    "ai_overviews": "Google AI Overviews",
    "chatgpt": "ChatGPT",
    "perplexity": "Perplexity",
}
