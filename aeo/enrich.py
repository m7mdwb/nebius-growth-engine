"""Track A enrichment — real lookups against real people.

A name, a surname and an email go in. A LinkedIn profile, a company record and an
explicit list of what we still do not know come out.

    email domain  ──▶ Serper: site:linkedin.com/in "Name" "Company"   (1 query)
                            │
                            ▼
                     Apify: person scrape                              (1 call)
                            │  gives currentPosition[0].companyLinkedinUrl
                            ▼
                     Apify: company scrape                             (1 call)
                            │
                            ▼
                     RECONCILE against the email domain  ──▶ verified | mismatch | thin

Three calls per lead, capped by `cost.Budget`. Field names below are **observed**, not
documented — every one was read off a live response by `scripts/probe.py` on
2026-08-15, because the actor READMEs disagree with the actors.

---

## 🔑 The rule that makes this safe: search only ever PROPOSES.

Serper's top hit for a human name is confidently, fluently the WRONG PERSON a good
share of the time, and nothing downstream can tell — the title looks real, the company
looks real, the scraped record is complete and well-formed. A lead scored on someone
else's career is not a blank record, it is a **confidently wrong one attached to a real
name**, and it is worse than no enrichment at all because it is invisible.

So a candidate profile is only accepted if it reconciles with something we already
hold. The one thing we hold for certain is the **email domain** — the lead typed it,
and it was not proposed by a search engine. `reconcile()` checks the scraped company's
own website against it. A mismatch routes to a human; it never scores.

(This is the same lesson as the job-finder resolver's `role_key` bug: every fetcher
stamped the company name we passed in, so the "verification" was comparing our own
string against itself and could never disagree. A check that cannot fail is not a
check. Here the email domain is the independent half.)

## ⚠️ Headcount growth is NOT available from one scrape.

The constraint says headcount and headcount growth off the LinkedIn company page are
the real growth proxy, and headcount is — `employeeCount` is right there. **Growth is
not.** `peopleStats` looked like it might carry it and does not: it is a breakdown of
where current employees sit, not a time series. LinkedIn exposes the company as it is
today and keeps no public history.

That is the same problem as Track C's, and it gets the same answer rather than a
guessed one: **headcount is stored as a timestamped snapshot every time we see a
company, and growth is computed on the SECOND sighting.** Until then it is `unknown`
and worth **zero points** — declared, never a zero that reads as "flat".

The alternative — asking a model to estimate growth — produces a number that is
fluent, specific, unfalsifiable and wrong, which is precisely what constraint 1 exists
to forbid.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .cost import Budget, apify_call, serper_search

# Observed working on 2026-08-15. See the note in scripts/probe.py: dev_fusion is the
# better-known actor but demands FULL ACCOUNT ACCESS and refuses to run until a human
# approves it once in the Apify console, so the shipping default is harvestapi — same
# vendor as the company actor, runs under LIMITED_PERMISSIONS, 50 fields per profile.
PERSON_ACTOR = "harvestapi~linkedin-profile-scraper"
COMPANY_ACTOR = "harvestapi~linkedin-company"

# ⚠️ The input key differs per actor and getting it wrong FAILS SILENTLY — handed
# `profileUrls`, harvestapi accepted the run, charged for it and returned zero items,
# which is indistinguishable from "this person has no profile". Keep them together.
PERSON_INPUT = {"harvestapi~linkedin-profile-scraper": "queries",
                "dev_fusion~linkedin-profile-scraper": "profileUrls"}

FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
             "proton.me", "protonmail.com", "gmx.de", "web.de", "aol.com", "mail.com",
             "yandex.ru", "live.com", "msn.com"}


def domain_of(email: str) -> str:
    return email.split("@")[-1].strip().lower() if "@" in email else ""


def host_of(url: str) -> str:
    try:
        h = (urlparse(url if "//" in url else "//" + url).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def registrable(host: str) -> str:
    """Crude eTLD+1. `careers.acme.co.uk` -> `acme.co.uk`.

    Deliberately crude: this feeds a *reconciliation* check, and the failure mode of
    being too strict (a human looks at it) is much cheaper than being too loose (a
    stranger's record gets scored as the lead).
    """
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    # Two-part public suffixes we actually meet in EU/UK B2B.
    if parts[-2] in {"co", "com", "org", "net", "ac", "gov"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def company_guess(domain: str) -> str:
    """A search term from the email domain. `kestrel-logistics.com` -> `kestrel logistics`."""
    label = registrable(domain).split(".")[0]
    return re.sub(r"[-_]+", " ", label).strip()


# ---------------------------------------------------------------------------
# step 1 — find the profile
# ---------------------------------------------------------------------------

def find_profile(first: str, last: str, domain: str, budget: Budget) -> dict:
    """One Serper query. Returns {url, candidates, query} — or an empty url."""
    name = f"{first} {last}".strip()
    guess = company_guess(domain)
    # The company term matters more than it looks. `site:linkedin.com/in "Jan Novak"`
    # returns hundreds of real people; adding the employer is what makes the top hit
    # meaningful. It is still only a proposal — see reconcile().
    query = f'site:linkedin.com/in "{name}"' + (f' "{guess}"' if guess else "")

    hits = serper_search(query, budget, what=f"profile: {name}", count=5)
    profiles = [h for h in hits if "linkedin.com/in/" in (h.get("url") or "")]
    return {
        "query": query,
        "url": profiles[0]["url"] if profiles else "",
        "candidates": [{"url": p["url"], "title": p["title"][:120]} for p in profiles[:5]],
    }


# ---------------------------------------------------------------------------
# step 2 — the person
# ---------------------------------------------------------------------------

def scrape_person(url: str, budget: Budget) -> dict:
    """Normalise a person record. Returns {} when nothing came back."""
    key = PERSON_INPUT.get(PERSON_ACTOR, "queries")
    items = apify_call(PERSON_ACTOR, {key: [url]}, budget, what=f"person: {url[-40:]}")
    if not items:
        return {}

    p = items[0]
    pos = (p.get("currentPosition") or p.get("experience") or [{}])[0] or {}
    loc = (p.get("location") or {}).get("parsed") or {}

    return {
        "linkedin_url": p.get("linkedinUrl") or url,
        "first_name": p.get("firstName"),
        "last_name": p.get("lastName"),
        # ⚠️ `headline` is self-written marketing ("Helping teams unlock AI!") and is a
        # bad input to a title-based seniority rule. The structured position is the
        # fact; the headline is the fallback and the colour for the draft.
        "title": pos.get("position") or p.get("headline"),
        "headline": p.get("headline"),
        "company_name": pos.get("companyName"),
        "company_linkedin": pos.get("companyLinkedinUrl"),
        "tenure": pos.get("duration"),
        "country": loc.get("countryCode") or (p.get("location") or {}).get("countryCode"),
        "location": loc.get("text") or (p.get("location") or {}).get("linkedinText"),
        "about": (p.get("about") or "")[:1200],
        "skills": [s.get("name") for s in (p.get("topSkills") or p.get("skills") or [])
                   if isinstance(s, dict) and s.get("name")][:12],
        "open_to_work": bool(p.get("openToWork")),
    }


# ---------------------------------------------------------------------------
# step 3 — the company
# ---------------------------------------------------------------------------

def _int_or_none(v) -> int | None:
    """`employeeCount` comes back as the STRING '233200'. Observed, not documented."""
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def scrape_company(url_or_name: str, budget: Budget) -> dict:
    items = apify_call(COMPANY_ACTOR, {"companies": [url_or_name]}, budget,
                       what=f"company: {url_or_name[-40:]}")
    if not items:
        return {}

    c = items[0]
    inds = c.get("industries") or []
    ind = inds[0] if inds and isinstance(inds[0], dict) else {}
    hq = next((l for l in (c.get("locations") or []) if l.get("headquarter")), None) \
        or (c.get("locations") or [{}])[0]
    rng = c.get("employeeCountRange") or {}

    return {
        "name": c.get("name"),
        "linkedin_url": c.get("linkedinUrl"),
        "website": c.get("website"),
        "headcount": _int_or_none(c.get("employeeCount")),
        "headcount_band": (f"{rng.get('start')}–{rng.get('end') or '+'}"
                           if rng.get("start") is not None else None),
        "industry": ind.get("name"),
        "industry_tree": ind.get("hierarchy"),
        "description": (c.get("description") or "")[:1500],
        "specialities": (c.get("specialities") or [])[:12],
        "hq": (hq.get("parsed") or {}).get("text") if hq else None,
        "hq_country": (hq.get("parsed") or {}).get("countryCode") if hq else None,
        "followers": c.get("followerCount"),
        "company_type": c.get("companyType"),
    }


# ---------------------------------------------------------------------------
# step 4 — reconcile. The step that makes the rest trustworthy.
# ---------------------------------------------------------------------------

def reconcile(person: dict, company: dict, email_domain: str) -> dict:
    """Is this scraped record actually the person who filled in the form?

    The email domain is the only fact a search engine did not propose, so it is the
    only thing worth checking against. Three outcomes, and the middle one is the
    reason this function exists.
    """
    ed = registrable(email_domain)
    site = registrable(host_of(company.get("website") or ""))

    if site and ed and site == ed:
        return {"verdict": "verified", "on": "company website matches the email domain",
                "detail": f"{site} == {ed}"}

    # Fall back to name similarity: plenty of companies list a marketing site on a
    # different domain from the one they issue email on. Weaker, and labelled weaker.
    cname = (company.get("name") or "").lower()
    guess = company_guess(email_domain)
    if cname and guess and (guess in cname or cname in guess):
        return {"verdict": "weak",
                "on": "company name resembles the email domain, but the website does not match",
                "detail": f"'{company.get('name')}' vs '{guess}'"
                          + (f" (site: {site})" if site else " (no website on the page)")}

    if not person and not company:
        return {"verdict": "thin", "on": "nothing was found to reconcile", "detail": ""}

    return {"verdict": "mismatch",
            "on": "the scraped company does not match the email domain",
            "detail": f"scraped '{company.get('name') or '?'}' ({site or 'no site'}) "
                      f"against '{ed}' — this may be a different person with the same name"}


# ---------------------------------------------------------------------------
# the waterfall
# ---------------------------------------------------------------------------

def enrich(lead: dict, budget: Budget) -> dict:
    """Run the whole lookup. Never raises except on budget — see cost.py.

    Returns a record that ALWAYS carries `unknowns`. A field we did not get is named
    there rather than defaulted to something falsy, because the scoring layer must be
    able to tell "zero" from "we never found out" — and so must the person reading it.
    """
    email = lead["email"]
    domain = domain_of(email)
    rec: dict = {
        "email": email, "domain": domain,
        "first_name": lead.get("first_name"), "last_name": lead.get("last_name"),
        "person": {}, "company": {}, "unknowns": [], "trace": [],
        "enriched": False, "reconciliation": None,
    }

    def note(msg: str) -> None:
        rec["trace"].append(msg)

    if not domain:
        rec["unknowns"].append("company_domain")
        note("no domain in the email address — nothing to look up")
        return rec

    if domain in FREE_MAIL:
        # Not a failure of enrichment. There is genuinely no company behind a personal
        # address, and spending two paid calls to confirm that is money for nothing.
        # The disqualifier layer handles it; this just refuses to pay to find out.
        note(f"{domain} is a personal mailbox — no company to look up, skipping paid calls")
        rec["unknowns"] += ["company", "headcount", "industry", "job_title"]
        return rec

    # --- 1. the profile -----------------------------------------------------
    found = find_profile(lead.get("first_name", ""), lead.get("last_name", ""),
                         domain, budget)
    rec["search"] = found
    if not found["url"]:
        note(f"no LinkedIn profile found for {found['query']}")
        rec["unknowns"].append("linkedin_profile")
    else:
        note(f"profile proposed: {found['url']}")
        rec["person"] = scrape_person(found["url"], budget)
        if not rec["person"]:
            note("profile page returned nothing")
            rec["unknowns"].append("person_record")

    # --- 2. the company -----------------------------------------------------
    # Prefer the company URL off the person's current position: it is the employer
    # LinkedIn itself links them to, which is stronger than anything we could guess.
    target = (rec["person"].get("company_linkedin")
              or rec["person"].get("company_name")
              or lead.get("company")
              or company_guess(domain))
    if target:
        note(f"company lookup: {target}")
        rec["company"] = scrape_company(target, budget)
    if not rec["company"]:
        note("no company record")
        rec["unknowns"] += ["company", "headcount", "industry"]

    # --- 3. reconcile -------------------------------------------------------
    rec["reconciliation"] = reconcile(rec["person"], rec["company"], domain)
    note(f"reconciliation: {rec['reconciliation']['verdict']} — {rec['reconciliation']['on']}")

    # --- 4. what we still do not know --------------------------------------
    c, p = rec["company"], rec["person"]
    if c and c.get("headcount") is None:
        rec["unknowns"].append("headcount")
    if c and not c.get("industry"):
        rec["unknowns"].append("industry")
    if p and not p.get("title"):
        rec["unknowns"].append("job_title")

    # 🔑 CONSTRAINT 1, stated in the record itself rather than only in a doc.
    # These are not obtainable for a private company and a model asked for them will
    # invent them fluently. They are named as unknown so they score zero explicitly,
    # and so nobody later mistakes their absence for an oversight.
    rec["unknowns"] += ["revenue", "valuation", "funding_total"]
    rec["never_guessed"] = ["revenue", "valuation", "funding_total"]
    # Growth needs a second sighting — see the module docstring. Filled in by
    # leads.py from the snapshot table when a prior observation exists.
    rec["unknowns"].append("headcount_growth")

    rec["enriched"] = bool(rec["company"]) and rec["reconciliation"]["verdict"] in ("verified", "weak")
    rec["unknowns"] = sorted(set(rec["unknowns"]))
    return rec
