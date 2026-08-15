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
from decimal import Decimal
from urllib.parse import urlparse

from .config import Config, env


@dataclass
class EngineResult:
    engine: str
    is_live: bool
    answer: str = ""
    citations: list[dict] = field(default_factory=list)   # {url, domain, title}
    # Everything the engine RETRIEVED, cited or not. Deliberately a separate field:
    # see the "search results are not citations" note above. Track C's source-gap
    # analysis needs both, and needs to keep them apart.
    retrieved: list[dict] = field(default_factory=list)
    # The organic SERP for the same query, where the surface exposes one. Only
    # AI Overviews does. Used to measure whether SEO feeds AEO — see analyze.py.
    serp: list[dict] = field(default_factory=list)
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

# ⚠️ MEASURED 2026-08-15 by scripts/probe.py, and it changed this function.
#
# Asked bare, the model routes its searches THROUGH THE CODE EXECUTION TOOL — it
# writes Python that awaits web_search(), reads the results itself, and writes prose
# from them. Search results consumed inside code carry no citation objects, so the
# answer comes back with `citations = None` on every text block. Measured: 6,326
# characters of confident answer and ZERO parseable citations.
#
# That failure is the dangerous kind, because it does not look like a failure. Every
# cell would classify as `mentioned`, never `cited`, and citation share — the one
# actionable metric on the page — would sit at a flat 0% that reads as a finding
# rather than as a broken instrument.
#
# The one line below fixes it: same query, 14 citations, stop_reason `end_turn`.
#
# 🔑 Why this does NOT corrupt the reading, which was the original objection to having
# a system prompt at all: it constrains HOW THE TOOL IS INVOKED, not what the answer
# may say. It names no brand, no competitor, no product category and no ranking
# criterion. The measurement stays a measurement of what the surface returns; it just
# returns it in a form where the links are attached to the sentences.
_DIRECT_SEARCH = (
    "Answer the question directly using web search. Do not use the code execution tool."
)

_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


def claude(query: str, cfg: Config) -> EngineResult:
    key = env("ANTHROPIC_API_KEY")
    if not key:
        return EngineResult("claude", False, note="no ANTHROPIC_API_KEY set")

    import anthropic

    model = cfg.engines.get("claude", {}).get("model", "claude-opus-5")
    # ⚠️ Also measured by the probe: at 1,500 tokens the turn ended on `max_tokens`
    # mid-sentence. A truncated answer under-reports every brand named after the cut,
    # which is a silent bias toward `absent` — so the ceiling is generous on purpose
    # and a truncated answer is flagged below rather than scored.
    max_tokens = int(cfg.engines.get("claude", {}).get("max_tokens", 4000))
    client = anthropic.Anthropic(api_key=key)

    def ask(messages: list[dict]):
        return client.messages.create(
            model=model, max_tokens=max_tokens, system=_DIRECT_SEARCH,
            tools=[_WEB_SEARCH_TOOL], messages=messages,
        )

    msgs = [{"role": "user", "content": query}]
    try:
        resp = ask(msgs)
    except Exception as exc:  # noqa: BLE001 - any failure is a recorded miss, not a crash
        return EngineResult("claude", True, error=f"{type(exc).__name__}: {exc}")

    # A long server-tool turn can stop early; resume once rather than reporting
    # a truncated answer as if it were the whole answer.
    if getattr(resp, "stop_reason", None) == "pause_turn":
        try:
            resp = ask(msgs + [{"role": "assistant", "content": resp.content}])
        except Exception as exc:  # noqa: BLE001
            return EngineResult("claude", True, error=f"resume failed: {exc}")

    if getattr(resp, "stop_reason", None) == "refusal":
        return EngineResult("claude", True, error="refused by safety classifier")

    text_parts: list[str] = []
    cites: dict[str, dict] = {}
    retrieved: dict[str, dict] = {}

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
        elif btype == "web_search_tool_result":
            # Everything the search returned, whether or not the answer used it.
            # Kept SEPARATE from citations on purpose — see the module docstring.
            # Track C's source-gap analysis reads this: a competitor's page that was
            # retrieved and not cited is a different (and weaker) finding than one the
            # answer actually linked, and merging them would inflate both.
            for item in (getattr(block, "content", None) or []):
                url = getattr(item, "url", None)
                if not url:
                    continue
                retrieved.setdefault(url, {
                    "url": url,
                    "domain": domain_of(url),
                    "title": getattr(item, "title", None) or "",
                })

    truncated = getattr(resp, "stop_reason", None) == "max_tokens"
    return EngineResult(
        "claude", True, answer="\n".join(text_parts).strip(),
        citations=list(cites.values()),
        retrieved=list(retrieved.values()),
        # Not an error — the answer is real, just incomplete. Recorded so a run
        # full of truncations is visible instead of reading as a drop in presence.
        note="answer truncated at max_tokens" if truncated else None,
    )


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

    from .cost import Budget, apify_call

    country = cfg.engines.get("ai_overviews", {}).get("country", "us")

    try:
        # ⚠️ This used to call the client directly with `timeout_secs=180`, which
        # apify-client 3.x does not accept — it was dead on arrival and had never been
        # run. Routed through the shared helper now, so it gets the spend cap too.
        items = apify_call(
            _APIFY_ACTOR,
            {
                "queries": query,
                "resultsPerPage": 10,
                "maxPagesPerQuery": 1,
                "countryCode": country,
                "languageCode": "en",
            },
            # One engine call, one budget — the AEO collector caps its own spend by
            # limiting how many queries it runs, not per call.
            Budget(apify_calls=1),
            what=f"AI Overviews: {query[:40]}",
            timeout_s=180,
            # This actor's declared minimum ceiling. A search costs a fraction of a
            # cent; $0.50 is the lowest cap it will accept, not the price.
            max_usd=Decimal("0.50"),
        )
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

    # 🔑 The organic SERP for the SAME query, captured because it is sitting right
    # there in the same response and it answers a question this whole category argues
    # about without evidence: DOES SEO FEED AEO?
    #
    # Everyone asserts it. Here it is measurable — compare the domains Google's AI
    # Overview chose to cite against the domains ranking organically underneath it.
    # High overlap means ranking is the lever and AEO is mostly SEO with extra steps;
    # low overlap means they are different games and an AEO programme needs its own
    # budget. `analyze.seo_overlap()` does the comparison; this just keeps the data.
    serp = []
    for i, o in enumerate(page.get("organicResults") or [], 1):
        url = o.get("url") or o.get("link") or ""
        if url:
            serp.append({"rank": i, "url": url, "domain": domain_of(url),
                         "title": (o.get("title") or "")[:120]})

    return EngineResult("ai_overviews", True, answer=str(answer).strip(),
                        citations=list(cites.values()), serp=serp)


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
