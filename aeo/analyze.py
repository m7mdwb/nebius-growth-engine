"""Turn an answer into observations.

Three decisions live here, and they are the ones a CMO would poke at. Each is
written down next to the code that implements it.

1. APPEARING IS NOT BINARY. Being cited with a link and being named in passing
   need different fixes, so they are different states. Collapsing them into
   "we appeared" is the flattening this tool exists to avoid.

2. THE CITED DOMAINS ARE THE ACTIONABLE OUTPUT. AI answers ground on third-party
   sources, so the lever is usually not your own site. Ranking the domains the
   answers actually cite turns a dashboard into a list of things to go and do.

3. NO COMPOSITE VISIBILITY SCORE. Every commercial tool in this space ships a
   0-100 number. One number that moves for reasons you cannot recover is worse
   than three you can act on, so presence rate, citation share and the
   competitor set are reported separately and never blended.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from .config import Config
from .engines import EngineResult, domain_of

CITED = "cited"
MENTIONED = "mentioned"
ABSENT = "absent"
UNMEASURED = "unmeasured"   # a seam. NOT a synonym for absent — see classify().

# Domains that get cited constantly and are nobody's competitor. Kept small and
# explicit — an over-eager stoplist would hide real players.
_PUBLISHER_DOMAINS = {
    "reddit.com", "wikipedia.org", "linkedin.com", "youtube.com", "medium.com",
    "quora.com", "forbes.com", "techcrunch.com", "g2.com", "capterra.com",
    "trustpilot.com", "glassdoor.com", "indeed.com", "x.com", "twitter.com",
    "facebook.com", "github.com", "stackoverflow.com", "coursereport.com",
}


def _pattern(term: str) -> re.Pattern:
    """Word-boundary match, tolerant of punctuation inside a name.

    Boundaries are applied only where the term actually starts or ends with a
    word character, so "O'Reilly" and "360Learning" behave.
    """
    esc = re.escape(term.strip())
    left = r"\b" if term[:1].isalnum() else ""
    right = r"\b" if term[-1:].isalnum() else ""
    return re.compile(f"{left}{esc}{right}", re.IGNORECASE)


def _first_index(text: str, terms: list[str]) -> int | None:
    best = None
    for t in terms:
        m = _pattern(t).search(text)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def _ambiguous_hit(text: str, rule: dict) -> int | None:
    """A bare ambiguous term counts only with supporting context nearby.

    "Nebius" alone is the parent AI-infrastructure company. An answer about GPU
    cloud is not an education-brand mention, and counting it would inflate the
    headline number in the flattering direction.
    """
    m = _pattern(rule["term"]).search(text)
    if not m:
        return None
    window = text[max(0, m.start() - 300): m.end() + 300].lower()
    if any(w.lower() in window for w in rule.get("requires_context", [])):
        return m.start()
    return None


def classify(result: EngineResult, cfg: Config) -> dict:
    """One answer -> one observation, plus its citations and competitors."""
    # A seam is stored as UNMEASURED, never as ABSENT. Writing "absent" for a
    # cell nobody read would put a fabricated negative into the table and let
    # every downstream rate quietly count it — the precise failure this tool
    # is built to detect in other people's dashboards.
    if not result.is_live:
        return {
            "status": UNMEASURED, "brand_rank": None, "products": [],
            "answer_chars": 0, "answer_excerpt": None,
            "citations": [], "competitors": [],
            "error": result.error, "note": result.note,
        }

    text = result.answer or ""

    owned = {d.lower() for d in cfg.owned_domains}
    cited_domains = {c["domain"] for c in result.citations if c.get("domain")}
    brand_is_cited = bool(owned & cited_domains)

    # --- brand presence ----------------------------------------------------
    brand_at = _first_index(text, cfg.brand_aliases)
    if brand_at is None:
        for rule in cfg.ambiguous:
            brand_at = _ambiguous_hit(text, rule)
            if brand_at is not None:
                break

    if brand_is_cited:
        status = CITED           # earned a link: the strongest form of presence
    elif brand_at is not None:
        status = MENTIONED       # named, but no link: recall without traffic
    else:
        status = ABSENT

    # --- products, tracked apart from the brand ---------------------------
    products_found = [
        p["name"] for p in cfg.products
        if _first_index(text, p.get("aliases") or [p["name"]]) is not None
    ]

    # --- competitors -------------------------------------------------------
    # Two routes. Seeds catch the names we already expect. Domain discovery
    # catches the ones we don't, which is the half that produces findings:
    # a competitor cited from its own domain announces itself.
    positions: dict[str, int] = {}
    for name in cfg.competitor_seeds:
        at = _first_index(text, [name])
        if at is not None:
            positions[name] = at

    discovered: set[str] = set()
    for d in sorted(cited_domains):
        if not d or d in owned or d in _PUBLISHER_DOMAINS:
            continue
        if any(d.endswith("." + o) or o.endswith("." + d) for o in owned):
            continue
        label = d.split(".")[0]
        if label and not any(_pattern(s).fullmatch(label) for s in positions):
            if label.lower() not in {p.lower() for p in positions}:
                discovered.add(d)

    # Rank by order of appearance in the answer; position is signal in an AI
    # answer, the same way it is in a SERP.
    ordered = sorted(positions.items(), key=lambda kv: kv[1])
    competitors = [
        {"name": n, "rank": i + 1, "discovered": 0} for i, (n, _) in enumerate(ordered)
    ]
    competitors += [
        {"name": d, "rank": None, "discovered": 1} for d in sorted(discovered)
    ]

    # The brand's own rank among everything named.
    brand_rank = None
    if brand_at is not None:
        brand_rank = 1 + sum(1 for _, at in ordered if at < brand_at)

    return {
        "status": status,
        "brand_rank": brand_rank,
        "products": products_found,
        "answer_chars": len(text),
        "answer_excerpt": text[:600],
        "citations": [
            {**c, "is_owned": 1 if c.get("domain", "").lower() in owned else 0}
            for c in result.citations
        ],
        "competitors": competitors,
        "error": result.error,
        "note": result.note,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def summarise(observations: list[dict], citations: list[dict],
              competitors: list[dict]) -> dict:
    """Roll one run up into the numbers the dashboard shows.

    Seams (is_live = 0) are excluded from every rate. A rate whose denominator
    silently includes unmeasured cells is the exact error this tool is built to
    catch, so it must not commit it.
    """
    live = [o for o in observations if o.get("is_live") and not o.get("error")]
    total = len(live)

    def rate(pred) -> float:
        return round(100 * sum(1 for o in live if pred(o)) / total, 1) if total else 0.0

    by_engine: dict[str, dict] = defaultdict(lambda: {"n": 0, "cited": 0, "mentioned": 0})
    for o in live:
        e = by_engine[o["engine"]]
        e["n"] += 1
        if o["status"] == CITED:
            e["cited"] += 1
        elif o["status"] == MENTIONED:
            e["mentioned"] += 1
    for e in by_engine.values():
        e["presence_rate"] = round(100 * (e["cited"] + e["mentioned"]) / e["n"], 1) if e["n"] else 0.0

    owned_cites = sum(1 for c in citations if c.get("is_owned"))
    citation_share = round(100 * owned_cites / len(citations), 1) if citations else 0.0

    domains = Counter(c["domain"] for c in citations if c.get("domain"))
    # Where competitors get cited and we do not — the action list.
    domain_rows = [
        {"domain": d, "citations": n,
         "is_owned": 1 if any(c.get("is_owned") and c["domain"] == d for c in citations) else 0}
        for d, n in domains.most_common(20)
    ]

    comp = Counter(c["name"] for c in competitors)
    comp_rows = [{"name": n, "appearances": c} for n, c in comp.most_common(15)]

    # Variance: the same query asked more than once. If these disagree, a single
    # snapshot is not a measurement — which is the point of collecting them.
    spread: dict[str, set] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    for o in live:
        key = f"{o['query_id']}|{o['engine']}"
        spread[key].add(o["status"])
        counts[key] += 1
    unstable = sum(1 for k, s in spread.items() if counts[k] > 1 and len(s) > 1)
    repeated = sum(1 for k in spread if counts[k] > 1)

    return {
        "observations": total,
        "presence_rate": rate(lambda o: o["status"] in (CITED, MENTIONED)),
        "cited_rate": rate(lambda o: o["status"] == CITED),
        "absent_rate": rate(lambda o: o["status"] == ABSENT),
        "citation_share": citation_share,
        "owned_citations": owned_cites,
        "total_citations": len(citations),
        "by_engine": dict(by_engine),
        "domains": domain_rows,
        "competitors": comp_rows,
        "variance": {
            "repeated_cells": repeated,
            "unstable_cells": unstable,
            "unstable_pct": round(100 * unstable / repeated, 1) if repeated else 0.0,
        },
    }
