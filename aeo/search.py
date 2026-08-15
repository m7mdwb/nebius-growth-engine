"""Web search — used to find the LinkedIn profile behind a name and an email.

Ported from the job-finder project's `src/pipeline/websearch.py`, whose parsers were
verified against live responses on 2026-08-10. Not rewritten from memory: the response
shapes below are observed, not documented.

Two things carry over unchanged because they are the whole safety argument:

🔑 **SEARCH ONLY EVER PROPOSES.** A result is a candidate, never an answer. Searching
for a person by name returns a confident, well-formatted profile of a *different human*
about as often as it returns the right one, and nothing downstream can tell the
difference — every field will look plausible. So a candidate profile is reconciled
against something we already hold (the email domain) before a single point is scored.
See `leads.reconcile()`.

⚠️ **A `QueryRejected` is not a dead backend.** Serper answers 400
`"Query pattern not allowed for free accounts"` to certain individual queries while the
same key happily answers the next twelve. Treating that as an outage cost a whole run
its search access once. It is a per-query signal and stays one.

Providers, in order: Serper (real Google, so `site:` behaves exactly as typed — this is
why it is first, since every query here is a `site:` query), then Exa as a fallback.
DuckDuckGo is deliberately absent: measured blocked on 2026-08-10 even from a
residential IP, and a keyless path that fails silently is worse than no path at all.
"""

from __future__ import annotations

import os

import httpx

SERPER = "https://google.serper.dev/search"
EXA = "https://api.exa.ai/search"


class QueryRejected(Exception):
    """This one query was refused. The backend itself is fine."""


_WARNED: set[str] = set()
# A provider that has started refusing us stays off for the rest of the run: a daily
# quota does not recover mid-run, and thirty more 429s only make the run slower.
_DISABLED: set[str] = set()


def _warn(msg: str) -> None:
    if msg not in _WARNED:
        _WARNED.add(msg)
        print(f"    search: {msg}", flush=True)


def providers() -> list[str]:
    out = []
    if os.getenv("SERPER_API_KEY"):
        out.append("serper")
    if os.getenv("EXA_API_KEY"):
        out.append("exa")
    return out


def live() -> bool:
    return any(p not in _DISABLED for p in providers())


def _serper(query: str, count: int) -> list[dict]:
    resp = httpx.post(
        SERPER,
        json={"q": query, "num": min(count, 20)},
        headers={"X-API-KEY": os.environ["SERPER_API_KEY"],
                 "Content-Type": "application/json"},
        timeout=20,
    )
    if resp.status_code == 400:
        raise QueryRejected(resp.text[:120])
    resp.raise_for_status()
    return [
        {"url": x.get("link") or "", "title": x.get("title") or "",
         "snippet": x.get("snippet") or ""}
        for x in ((resp.json() or {}).get("organic") or [])
        if x.get("link")
    ]


def _exa(query: str, count: int) -> list[dict]:
    resp = httpx.post(
        EXA,
        json={"query": query, "numResults": min(count, 25), "type": "auto"},
        headers={"x-api-key": os.environ["EXA_API_KEY"], "Content-Type": "application/json"},
        timeout=25,
    )
    if resp.status_code == 400:
        raise QueryRejected(resp.text[:120])
    resp.raise_for_status()
    return [
        {"url": x.get("url") or "", "title": x.get("title") or "",
         "snippet": x.get("snippet") or ""}
        for x in ((resp.json() or {}).get("results") or [])
        if x.get("url")
    ]


_BACKENDS = {"serper": _serper, "exa": _exa}


def search(query: str, count: int = 10) -> list[dict]:
    """Return [{url, title, snippet}]. Empty list on any failure — never raises."""
    for name in providers():
        if name in _DISABLED:
            continue
        try:
            hits = _BACKENDS[name](query, count)
        except QueryRejected as e:
            _warn(f"{name} refused a query — {str(e)[:90]}")
            continue
        except Exception as e:  # noqa: BLE001
            _DISABLED.add(name)
            _warn(f"{name} off for this run — {type(e).__name__}: {str(e)[:100]}")
            continue
        if hits:
            return hits
    return []
