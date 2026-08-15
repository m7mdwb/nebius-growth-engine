"""What a call actually cost, read from the response rather than estimated.

This module exists because of a question I could not answer without guessing:
*how much did that run cost?* The honest answer at the time was a reconstruction
from call counts and stored answer lengths, with a range of roughly 2x — because
nothing recorded `response.usage`, even though every response carries it.

⚠️ The single biggest term is the one an estimate gets most wrong. A Track C call
uses the web_search tool, and **search results are injected into the input**, so a
one-line query can arrive at the model as 30,000+ input tokens. Output tokens are
visible in the answer and easy to approximate; input tokens are invisible and
dominate the bill. Estimating from what you can see systematically under-counts the
half you cannot.

Two things follow, and the second matters more:

  1. Cost becomes a SQL query instead of an argument.
  2. Spend is visible DURING a run, not after it. The run that prompted this file
     died at call one of eighty on an exhausted credit balance and reported it at
     the end — every Claude cell was a 400 and nothing said so until the run was
     over. Per-call usage is what makes that legible while it is happening.

Prices are USD per million tokens, read from the Anthropic pricing table on
2026-08-15. They are here rather than inline so a price change is one edit and a
diff, the same principle as the query set and the fit definition.
"""

from __future__ import annotations

from datetime import date

# (input, output) per million tokens.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# ⚠️ Sonnet 5 is on introductory pricing until this date, after which it reverts
# to the table above. Dated rather than hardcoded, so the number stops being right
# on its own instead of quietly overstating our costs for the rest of the year.
SONNET_INTRO_UNTIL = date(2026, 8, 31)
SONNET_INTRO = (2.00, 10.00)

# The term an estimate always forgets. $10 per 1,000 searches, and a single Track C
# call can make up to `max_uses` of them — at max_uses=5 the search line alone can
# exceed the token line for that call.
WEB_SEARCH_PER_1K = 10.00

# Cache multipliers against the input rate.
CACHE_WRITE_MULT = 1.25
CACHE_READ_MULT = 0.10


def rates(model: str, on: date | None = None) -> tuple[float, float]:
    on = on or date.today()
    if model.startswith("claude-sonnet-5") and on <= SONNET_INTRO_UNTIL:
        return SONNET_INTRO
    for key, price in PRICES.items():
        if model.startswith(key):
            return price
    return (0.0, 0.0)      # unknown model: report zero rather than invent a price


def usage_of(resp) -> dict:
    """Pull the usage numbers off a Messages response. Total, never raising.

    Written defensively on purpose: this runs inside the collector, and a usage
    field that moves between SDK versions must never be able to kill a paid run
    that has already done its work.
    """
    u = getattr(resp, "usage", None)
    if u is None:
        return {}
    st = getattr(u, "server_tool_use", None)
    return {
        "model": getattr(resp, "model", None),
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "web_searches": (getattr(st, "web_search_requests", 0) or 0) if st else 0,
    }


def cost_usd(usage: dict, model: str | None = None, on: date | None = None) -> float:
    """USD for one call. Returns 0.0 for an empty usage dict."""
    if not usage:
        return 0.0
    inp, out = rates(model or usage.get("model") or "", on)
    per_tok_in = inp / 1_000_000
    return round(
        usage.get("input_tokens", 0) * per_tok_in
        + usage.get("output_tokens", 0) * out / 1_000_000
        + usage.get("cache_write_tokens", 0) * per_tok_in * CACHE_WRITE_MULT
        + usage.get("cache_read_tokens", 0) * per_tok_in * CACHE_READ_MULT
        + usage.get("web_searches", 0) * WEB_SEARCH_PER_1K / 1000,
        6,
    )


def summarise(rows: list[dict]) -> dict:
    """Roll usage rows up into the line a run prints when it finishes."""
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
           "cache_read_tokens": 0, "web_searches": 0, "usd": 0.0}
    for r in rows:
        if not r:
            continue
        tot["calls"] += 1
        for k in ("input_tokens", "output_tokens", "cache_read_tokens", "web_searches"):
            tot[k] += r.get(k, 0) or 0
        tot["usd"] += cost_usd(r)
    tot["usd"] = round(tot["usd"], 4)
    return tot
