"""Step 0. Prove every integration works before anything is built on it.

    python scripts/probe.py            # all five, one call each
    python scripts/probe.py --only 3   # just one
    python scripts/probe.py --list

Zero real API calls had been made against this codebase when the project started.
Every adapter in it was written from documentation and had never once been run. That
is the single biggest risk in the build, because a mocked prototype and a broken
integration look identical from the outside — both produce a dashboard full of
plausible cells — and the difference only surfaces on camera.

So: **one call per integration, PASS/FAIL, and the actual data shape printed.** Not a
smoke test that checks for a 200. The shape is the deliverable here, because the
enrichment adapter gets written against observed keys rather than documented ones, and
scraper output drifts from its own docs constantly.

Three rules this file exists to enforce:

1. **It probes the REAL adapters**, not reimplementations of them. Probe 1 calls
   `engines.claude()` and probe 5 calls `leads.draft()`. A probe that passes while the
   shipping code path is broken is worse than no probe, and rewriting the call inline
   is exactly how that happens.
2. **Any integration that fails twice becomes a marked seam within 30 minutes.** It does
   not get debugged into the deadline. The prototype already knows how to render a seam
   honestly; that is the fallback and it is a good one.
3. **One call each.** A retry loop against a paid actor is real money, and this file is
   the thing most likely to be run over and over.

Costs, from the Apify actor definitions on 2026-08-15:
  dev_fusion/linkedin-profile-scraper   $0.01 per profile
  harvestapi/linkedin-company           $0.00005 start + per-company charge
  Serper                                ~$0.001 per query (2,500 free credits)
  Anthropic                             a few cents per probe run
A full probe run is well under five cents.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252 and a scraper's emoji-laden title will raise
# UnicodeEncodeError mid-probe, which reads as an integration failure when it is a
# terminal setting. Fail on the integration, never on the print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from aeo import config, cost, leads, search  # noqa: E402
from aeo.engines import claude as claude_engine  # noqa: E402

# A deliberately PUBLIC test subject. Two reasons: the correct answer is already known,
# so "it returned something" can be told apart from "it returned the right thing" — and
# no private person's scraped record ends up in a probe log that gets pasted around.
SUBJECT = {"name": "Satya Nadella", "company": "Microsoft",
           "profile": "https://www.linkedin.com/in/satyanadella",
           "company_url": "https://www.linkedin.com/company/microsoft"}

# Person scrapers, tried in order. dev_fusion is the one named in the spec and has the
# most runs on the store; harvestapi is the fallback and is the same vendor as the
# company actor, so both records come from one source of truth.
#
# ⚠️ THE INPUT KEY IS NOT THE SAME, and getting it wrong is silent. dev_fusion takes
# `profileUrls`; harvestapi takes `queries`. Handed `profileUrls`, harvestapi accepted
# the run, charged for the start, and returned ZERO ITEMS WITH NO ERROR — which is
# indistinguishable from "that person has no LinkedIn profile". An empty result that
# means "you called it wrong" is the worst possible shape for a failure, and it is
# exactly what a mocked prototype would never have caught.
PERSON_ACTORS = [
    ("dev_fusion~linkedin-profile-scraper", lambda url: {"profileUrls": [url]}),
    ("harvestapi~linkedin-profile-scraper", lambda url: {"queries": [url]}),
]
COMPANY_ACTOR = "harvestapi~linkedin-company"

OUT = Path(__file__).resolve().parent.parent / "out"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def shape(obj, depth: int = 0, limit: int = 24) -> str:
    """Render what came back, not what the docs promised."""
    pad = "  " * (depth + 1)
    if isinstance(obj, dict):
        lines = []
        for k, v in list(obj.items())[:limit]:
            if isinstance(v, dict):
                lines.append(f"{pad}{k}: dict({len(v)} keys) {list(v)[:6]}")
            elif isinstance(v, list):
                inner = f" of {type(v[0]).__name__}" if v else ""
                lines.append(f"{pad}{k}: list[{len(v)}]{inner}")
            else:
                s = str(v).replace("\n", " ")
                lines.append(f"{pad}{k}: {type(v).__name__} = {s[:70]}")
        if len(obj) > limit:
            lines.append(f"{pad}... {len(obj) - limit} more keys")
        return "\n".join(lines)
    return f"{pad}{type(obj).__name__}: {str(obj)[:200]}"


def apify_call(actor: str, run_input: dict) -> list[dict]:
    """One call, through the SHIPPING helper — rule 1. It carries the spend cap."""
    return cost.apify_call(actor, run_input, cost.Budget(apify_calls=1),
                           what=f"probe {actor}")


# ---------------------------------------------------------------------------
# the five probes. Each returns (passed, detail, evidence)
# ---------------------------------------------------------------------------

def probe_1_claude_websearch() -> tuple[bool, str, dict]:
    """Claude + web_search_20260209 — does the answer carry PARSEABLE citations?

    The distinction that matters: an answer with no citations attached is not the same
    failure as a tool that did not run. The first means Track C can measure *mentioned*
    but never *cited*, which would silently halve the instrument — every cell would read
    'mentioned' and the citation-share metric, which is the actionable one, would be a
    flat zero that looks like a finding.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False, "no ANTHROPIC_API_KEY", {}

    cfg = config.load()
    res = claude_engine("best AI readiness training for enterprises", cfg)

    if res.error:
        return False, f"engine error: {res.error}", {}
    if not res.answer:
        return False, "empty answer — web_search tool may not have run", {}

    n = len(res.citations)
    parseable = [c for c in res.citations if c.get("url") and c.get("domain")]
    ev = {"answer_chars": len(res.answer), "citations": n,
          "parseable": len(parseable),
          "retrieved_not_cited": len({r["domain"] for r in res.retrieved}
                                     - {c["domain"] for c in parseable}),
          "note": res.note,
          "sample": parseable[:4],
          "domains": sorted({c["domain"] for c in parseable})[:12]}

    if not parseable:
        return False, (f"answered {len(res.answer)} chars but attached ZERO parseable "
                       f"citations — Track C could measure 'mentioned' but never 'cited'"), ev
    return True, f"{len(parseable)}/{n} citations carry url+domain", ev


def probe_2_serper() -> tuple[bool, str, dict]:
    """Serper — does `site:linkedin.com/in "Name" "Company"` return a profile URL?

    This is the first hop of Track A: an email and a name is all the form gives us, and
    without a LinkedIn URL there is nothing for the scrapers to scrape.
    """
    if not os.getenv("SERPER_API_KEY"):
        return False, "no SERPER_API_KEY", {}

    q = f'site:linkedin.com/in "{SUBJECT["name"]}" "{SUBJECT["company"]}"'
    hits = search.search(q, count=5)
    if not hits:
        return False, "zero results (provider refused, or genuinely nothing)", {"query": q}

    profiles = [h for h in hits if "linkedin.com/in/" in (h.get("url") or "")]
    ev = {"query": q, "results": len(hits), "profile_urls": len(profiles),
          "top": [{"url": h["url"], "title": h["title"][:70]} for h in hits[:3]]}

    if not profiles:
        return False, f"{len(hits)} results but none is a /in/ profile URL", ev
    ev["chosen"] = profiles[0]["url"]
    # Known-answer check. "It returned a URL" is not the same as "it returned the
    # right person", and only a subject whose answer we already know can tell them apart.
    ok = "satyanadella" in profiles[0]["url"].lower()
    return ok, (f"top profile {profiles[0]['url']}"
                + ("" if ok else "  ⚠ NOT the expected subject — ranking is not identity")), ev


def probe_3_apify_person() -> tuple[bool, str, dict]:
    """Apify dev_fusion/linkedin-profile-scraper — one profile.

    Prints the raw top-level keys, because the enrichment adapter is written against
    these and not against the actor's README.
    """
    if not os.getenv("APIFY_TOKEN"):
        return False, "no APIFY_TOKEN", {}

    # ⚠️ dev_fusion demands FULL ACCOUNT ACCESS and refuses to run until a human
    # approves it once in the Apify console. That is a store-permission gate, not an
    # outage and not something code can work around — so rather than burn the deadline
    # on it, the fallback is the same vendor as the company actor, which runs under
    # LIMITED_PERMISSIONS. Whichever answers first is the one the adapter ships with.
    attempts, items, actor_used = [], [], None
    for actor, build_input in PERSON_ACTORS:
        try:
            items = apify_call(actor, build_input(SUBJECT["profile"]))
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"{actor}: {type(exc).__name__}: {str(exc)[:120]}")
            continue
        if items:
            actor_used = actor
            break
        attempts.append(f"{actor}: returned no items")

    if not items:
        return False, "no person scraper answered", {"attempts": attempts}

    it = items[0]
    # What Track A actually needs off a person: a current title and a current employer.
    # Everything else is colour for the draft.
    title = it.get("headline") or it.get("jobTitle") or it.get("occupation")
    ev = {"actor_used": actor_used, "attempts": attempts,
          "keys": sorted(it.keys()), "n_items": len(items),
          "title_candidates": {k: str(it.get(k))[:90] for k in
                               ("headline", "jobTitle", "occupation", "position") if it.get(k)},
          "company_candidates": {k: str(it.get(k))[:90] for k in
                                 ("companyName", "company", "currentCompany", "currentPosition",
                                  "companyIndustry", "experience", "experiences") if it.get(k)}}
    return bool(title), f"{actor_used} — {len(it)} fields; title={'yes' if title else 'NO'}", ev


def probe_4_apify_company() -> tuple[bool, str, dict]:
    """Apify harvestapi/linkedin-company — one company.

    The one field this whole constraint rests on: **headcount, and headcount growth.**
    Revenue and valuation are not obtainable for private companies and a model asked for
    them will invent them, so employee count off the company page is the growth proxy
    and everything else is an explicit unknown worth zero points.
    """
    if not os.getenv("APIFY_TOKEN"):
        return False, "no APIFY_TOKEN", {}

    items = apify_call(COMPANY_ACTOR, {"companies": [SUBJECT["company_url"]]})
    if not items:
        return False, "actor returned no items", {}

    it = items[0]
    hc_keys = [k for k in it if "employee" in k.lower() or "headcount" in k.lower()
               or "size" in k.lower() or "staff" in k.lower()]
    ev = {"keys": sorted(it.keys()), "n_items": len(items),
          "headcount_fields": {k: str(it.get(k))[:120] for k in hc_keys},
          "industry": str(it.get("industry") or it.get("industries"))[:120]}
    return bool(hc_keys), (f"{len(it)} fields; headcount fields: {hc_keys or 'NONE'}"), ev


def probe_5_drafting() -> tuple[bool, str, dict]:
    """Anthropic drafting with a JSON schema — does it return facts_used?

    `facts_used` is not decoration. It is the only thing separating 'personalised' as a
    claim from 'personalised' as something you can check in one glance — a draft citing
    no facts is a mail-merge in costume. If the schema does not come back honoured, the
    audit disappears and the feature is worth much less.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return False, "no ANTHROPIC_API_KEY", {}

    fit = leads.load_fit()
    lead = {"first_name": "Karin", "last_name": "Andersen",
            "email": "k.andersen@meridianbank.com", "company": "Meridian Bank",
            "source": "completed_assessment", "signals": ["completed_assessment"],
            "note": "Assessment score: 2.1/5 on AI readiness"}
    enriched = {"company": "Meridian Bank", "industry": "Financial services",
                "headcount": 8200, "title": "Chief People Officer",
                "seniority": "exec", "function": "People", "domain": "meridianbank.com"}
    breakdown = [{"factor": "Headcount", "detail": "8,200 employees", "points": 25}]
    routing = {"route": "hot", "sla_minutes": 5}

    d = leads.draft(lead, enriched, breakdown, routing, fit)
    if d.get("error"):
        return False, f"draft error: {d['error']}", {"raw": str(d.get("raw"))[:300]}

    facts = d.get("facts_used")
    ev = {"returned_keys": sorted(d.keys()), "subject": d.get("subject"),
          "facts_used": facts, "message_words": len((d.get("message") or "").split()),
          "message_head": (d.get("message") or "")[:200]}
    if not isinstance(facts, list):
        return False, "schema not honoured — facts_used missing or not a list", ev
    if not facts:
        return False, "facts_used came back EMPTY — that is a mail-merge", ev
    return True, f"schema honoured, {len(facts)} facts cited", ev


PROBES = [
    ("Claude + web_search_20260209 — parseable citations", probe_1_claude_websearch),
    ('Serper — site:linkedin.com/in "Name" "Company"', probe_2_serper),
    ("Apify dev_fusion/linkedin-profile-scraper — one profile", probe_3_apify_person),
    ("Apify harvestapi/linkedin-company — one company", probe_4_apify_company),
    ("Anthropic drafting, JSON schema — facts_used", probe_5_drafting),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="One call per integration. PASS/FAIL + shape.")
    ap.add_argument("--only", type=int, help="run a single probe by number (1-5)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        for i, (name, _) in enumerate(PROBES, 1):
            print(f"  {i}. {name}")
        return 0

    chosen = [(i, *PROBES[i - 1]) for i in ([a.only] if a.only else range(1, len(PROBES) + 1))]

    print("=" * 78)
    print("INTEGRATION PROBE — one call each, nothing gets built on an unverified adapter")
    print("=" * 78)

    report, failures = [], 0
    for n, name, fn in chosen:
        print(f"\n[{n}/{len(PROBES)}] {name}")
        print("-" * 78)
        try:
            passed, detail, ev = fn()
        except Exception as exc:  # noqa: BLE001 — one dead probe must not kill the rest
            passed, detail, ev = False, f"{type(exc).__name__}: {exc}", {}

        print(f"  {'PASS' if passed else 'FAIL'}  {detail}")
        if ev:
            print("  shape:")
            print(shape(ev))
        failures += 0 if passed else 1
        report.append({"n": n, "name": name, "passed": passed,
                       "detail": detail, "evidence": ev})

    print("\n" + "=" * 78)
    ok = len(chosen) - failures
    print(f"{ok}/{len(chosen)} PASS")
    if failures:
        print("\nFailures become MARKED SEAMS within 30 minutes. They do not get debugged")
        print("into the deadline — the dashboard already renders a seam honestly.")

    OUT.mkdir(exist_ok=True)
    # out/ is gitignored: a probe log holds scraped fields and must not be committed.
    path = OUT / "probe_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")
    print(f"\nfull evidence -> {path}  (gitignored)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
