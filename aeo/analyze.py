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
            "citations": [], "competitors": [], "serp_domains": [],
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
        "serp_domains": [s["domain"] for s in (result.serp or []) if s.get("domain")],
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


# ---------------------------------------------------------------------------
# The benchmark: "we appear in N of 10". A COUNT, never a percentage.
# ---------------------------------------------------------------------------

def benchmark(observations: list[dict], cfg: Config) -> dict:
    """Ten named queries, each won or lost, and the score is how many we won.

    🔑 Why a count rather than a rate. A percentage hides its denominator, and the
    denominator is where these dashboards lie: 30% reads the same whether it is 3 of
    10 measured or 3 of 10 with four cells never looked at. A count forces the
    denominator onto the page. It also turns the target from "improve visibility" —
    which nobody can action — into "we lose these seven specific questions, and here
    is who wins them instead", which someone can pick up on Monday.

    ⚠️ Branded queries are excluded. `benchmark: false` in queries.yaml. Asking "what
    is Nebius Academy" and counting the answer as a win is free marks.

    A query counts as WON if any engine cited or mentioned us on any repeat. That is
    deliberately generous: the point of the headline number is "did we show up at all
    anywhere", and the cited-vs-mentioned distinction is carried in the detail rows
    where it can be acted on rather than being averaged into the top line.
    """
    ids = [q.id for q in cfg.queries if getattr(q, "benchmark", True)]
    by_q: dict[str, list[dict]] = defaultdict(list)
    for o in observations:
        if o["query_id"] in ids:
            by_q[o["query_id"]].append(o)

    rows = []
    for q in cfg.queries:
        if not getattr(q, "benchmark", True):
            continue
        obs = by_q.get(q.id, [])
        live = [o for o in obs if o.get("is_live") and not o.get("error")]
        statuses = {o["status"] for o in live}
        if not live:
            state = UNMEASURED      # never counted as a loss
        elif CITED in statuses:
            state = CITED
        elif MENTIONED in statuses:
            state = MENTIONED
        else:
            state = ABSENT
        rows.append({
            "query_id": q.id, "query": q.text, "intent": q.intent, "state": state,
            "won": state in (CITED, MENTIONED),
            "engines_measured": len({o["engine"] for o in live}),
        })

    measured = [r for r in rows if r["state"] != UNMEASURED]
    won = [r for r in measured if r["won"]]
    return {
        "appear_in": len(won),
        "out_of": len(rows),
        "measured": len(measured),
        # Unmeasured queries are named, not folded into the denominator. If two of
        # ten were never asked, "3 of 10" is a different claim from "3 of 8" and the
        # reader is entitled to know which.
        "unmeasured": [r["query_id"] for r in rows if r["state"] == UNMEASURED],
        "cited": sum(1 for r in measured if r["state"] == CITED),
        "mentioned": sum(1 for r in measured if r["state"] == MENTIONED),
        "target": len(rows),
        "rows": rows,
        "lost": [r for r in measured if not r["won"]],
    }


# ---------------------------------------------------------------------------
# The source gap: what the answers cite where we lose, and what kind of thing it is
# ---------------------------------------------------------------------------

# Deterministic classification. The MODEL does not decide what kind of source
# something is — that is a lookup, and a lookup that changes its mind between runs
# would make the recommendations unreproducible. Same rule as Track A's scoring.
_REVIEW_PLATFORMS = {
    "g2.com", "capterra.com", "trustradius.com", "trustpilot.com", "gartner.com",
    "softwareadvice.com", "sourceforge.net", "getapp.com", "peerspot.com",
    "clutch.co", "coursereport.com", "switchup.org", "producthunt.com",
}
_COMMUNITY = {"reddit.com", "quora.com", "news.ycombinator.com", "stackoverflow.com",
              "stackexchange.com", "x.com", "twitter.com", "linkedin.com"}
_MAJOR_PUBLISHERS = {
    "forbes.com", "techcrunch.com", "hbr.org", "mckinsey.com", "bcg.com",
    "deloitte.com", "pwc.com", "ey.com", "accenture.com", "gartner.com",
    "wired.com", "ft.com", "economist.com", "wsj.com", "bloomberg.com",
    "venturebeat.com", "zdnet.com", "cio.com", "computerworld.com",
}

SOURCE_KINDS = {
    "owned": "Our own domains",
    "review_platform": "Review & comparison platforms",
    "competitor_owned": "A competitor's own site",
    "major_publisher": "Analyst & major press",
    "community": "Community & social",
    "editorial": "Independent blogs, listicles & roundups",
}


def classify_domain(domain: str, cfg: Config, competitor_names: set[str]) -> str:
    d = (domain or "").lower()
    if not d:
        return "editorial"
    owned = {o.lower() for o in cfg.owned_domains}
    if d in owned or any(d.endswith("." + o) for o in owned):
        return "owned"
    if d in _REVIEW_PLATFORMS:
        return "review_platform"
    if d in _COMMUNITY:
        return "community"
    if d in _MAJOR_PUBLISHERS:
        return "major_publisher"
    # A competitor cited from its own domain announces itself. Match the domain's
    # first label against the competitor names we hold, collapsed to alphanumerics
    # so "360Learning" matches "360learning.com" and "LinkedIn Learning" does not
    # accidentally match "linkedin.com" (which is classified as community above).
    label = re.sub(r"[^a-z0-9]", "", d.split(".")[0])
    for name in competitor_names:
        flat = re.sub(r"[^a-z0-9]", "", name.lower())
        if flat and label and (flat == label or (len(flat) > 5 and flat in label)):
            return "competitor_owned"
    return "editorial"


def source_gap(observations: list[dict], citations: list[dict],
               competitors: list[dict], cfg: Config) -> dict:
    """Where competitors are cited and we are not — and what KIND of source it is.

    This is the half that turns a scoreboard into a to-do list. Knowing we lose
    "best corporate AI upskilling programs" is not actionable. Knowing that the
    answers to it cite G2, two competitor blogs and a Forbes roundup — and that we
    are on none of them — names four specific places to go and get placed.
    """
    names = {c["name"] for c in competitors} | {s for s in cfg.competitor_seeds}
    owned = {o.lower() for o in cfg.owned_domains}

    bench_ids = {q.id for q in cfg.queries if getattr(q, "benchmark", True)}
    q_text = {q.id: q.text for q in cfg.queries}

    # Queries we did not win, from the live observations only.
    lost_ids = set()
    for qid in bench_ids:
        live = [o for o in observations
                if o["query_id"] == qid and o.get("is_live") and not o.get("error")]
        if live and not any(o["status"] in (CITED, MENTIONED) for o in live):
            lost_ids.add(qid)

    kinds: Counter = Counter()
    kind_domains: dict[str, Counter] = defaultdict(Counter)
    per_query: dict[str, dict] = {}

    for c in citations:
        if c["query_id"] not in lost_ids:
            continue
        kind = classify_domain(c.get("domain", ""), cfg, names)
        kinds[kind] += 1
        kind_domains[kind][c["domain"]] += 1
        q = per_query.setdefault(c["query_id"],
                                 {"query": q_text.get(c["query_id"], c["query_id"]),
                                  "domains": Counter(), "kinds": Counter()})
        q["domains"][c["domain"]] += 1
        q["kinds"][kind] += 1

    # Do we appear on ANY of the source types that win these queries? This is the
    # sentence that makes the finding land: not "we are absent", but "the answers
    # that beat us lean on review platforms 14 times and we are on none of them".
    our_kinds: Counter = Counter()
    for c in citations:
        if (c.get("domain") or "").lower() in owned:
            our_kinds["owned"] += 1

    return {
        "lost_queries": len(lost_ids),
        "kinds": [
            {"kind": k, "label": SOURCE_KINDS.get(k, k), "citations": n,
             "we_appear": k == "owned",
             "top_domains": [{"domain": d, "n": c}
                             for d, c in kind_domains[k].most_common(6)]}
            for k, n in kinds.most_common()
        ],
        "per_query": [
            {"query_id": qid, "query": v["query"],
             "domains": [{"domain": d, "n": n} for d, n in v["domains"].most_common(8)],
             "kinds": dict(v["kinds"])}
            for qid, v in per_query.items()
        ],
        "owned_citations_anywhere": sum(our_kinds.values()),
    }


def seo_overlap(rows: list[dict]) -> dict:
    """Does SEO feed AEO? Measured, not asserted.

    `rows` is [{query_id, cited_domains, serp_domains}] built by the caller from the
    AI Overviews engine, which is the only surface that hands back both the generative
    answer and the organic results underneath it.

    The number that matters is what share of the domains an AI answer CITED were also
    ranking organically for the same query. High overlap says ranking is still the
    lever and an AEO programme is mostly an SEO programme with different reporting.
    Low overlap says they are separate games and the budget has to be separate too.

    ⚠️ Reported with its sample size attached, because on a handful of queries this
    number swings wildly and a single figure would be read as settled.
    """
    pairs, hits, total = 0, 0, 0
    detail = []
    for r in rows:
        cited = {d for d in (r.get("cited_domains") or []) if d}
        serp = {d for d in (r.get("serp_domains") or []) if d}
        if not cited or not serp:
            continue
        pairs += 1
        overlap = cited & serp
        hits += len(overlap)
        total += len(cited)
        detail.append({"query_id": r["query_id"], "cited": len(cited),
                       "also_ranking": len(overlap),
                       "domains": sorted(overlap)[:6]})
    return {
        "queries_compared": pairs,
        "cited_domains": total,
        "also_ranking_organically": hits,
        "overlap_pct": round(100 * hits / total, 1) if total else None,
        "detail": detail,
        "verdict": (None if pairs < 3 else
                    "SEO strongly feeds AEO here — the answers mostly cite what already ranks"
                    if total and hits / total >= 0.5 else
                    "SEO and AEO are diverging — the answers cite sources that are not the "
                    "top organic results, so ranking alone will not buy citations"),
    }
