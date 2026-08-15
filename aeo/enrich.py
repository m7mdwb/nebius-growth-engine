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

from .cost import ActorRefused, Budget, apify_call, serper_search

# Person scrapers, tried in order, because neither is dependable alone on a free plan:
#
#   dev_fusion  — the better-known actor (23.8M runs) and no per-plan run cap, but it
#                 demands FULL ACCOUNT ACCESS and refuses until a human approves it
#                 once in the Apify console. Approval is a click; nothing in code can
#                 do it. First in the list so it takes over the moment it is granted.
#   harvestapi  — runs under LIMITED_PERMISSIONS with no approval, 50 fields per
#                 profile, same vendor as the company actor. ⚠️ But it caps FREE
#                 Apify accounts at 20 runs, and past that it returns a refusal
#                 *as a dataset item* rather than failing — see cost.ActorRefused.
#
# ⚠️ The input key differs per actor and getting it wrong FAILS SILENTLY — handed
# `profileUrls`, harvestapi accepted the run, charged for it and returned zero items,
# which is indistinguishable from "this person has no profile". Keep them together.
PERSON_ACTORS = [
    ("dev_fusion~linkedin-profile-scraper", "profileUrls"),
    ("harvestapi~linkedin-profile-scraper", "queries"),
]
# The company actor has its own separate run count and was still answering when the
# person actor had capped out — so a person-side block does not imply a company-side
# one, and each is reported on its own.
COMPANY_ACTOR = "harvestapi~linkedin-company"

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

def find_company_page(domain: str, name_hint: str, budget: Budget) -> str:
    """Find the company's LinkedIn page URL. One Serper query.

    ⚠️ Only used when the PERSON record didn't carry `companyLinkedinUrl`, which is
    the preferred key because LinkedIn itself asserts the person→employer link.
    That field is not always present — the same profile returned it one day and not
    the next — and without it the company lookup falls back to a bare name like
    "personio", which the company actor answers with nothing. The result was a
    perfectly enrichable lead landing in `needs_review` for want of a URL.

    Searching for the page is the fix, and it is safe for the usual reason: this
    only ever proposes. Whatever comes back still has to reconcile against the
    email domain before a single point is scored.
    """
    q = f'site:linkedin.com/company "{name_hint}"'
    hits = serper_search(q, budget, what=f"company page: {name_hint}", count=5)
    for h in hits:
        url = h.get("url") or ""
        if "linkedin.com/company/" in url:
            return url.split("?")[0]
    return ""


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

def _skills(raw) -> list[str]:
    """Skills arrive as dicts from one actor and bare strings from the other."""
    out = []
    for s in (raw or [])[:14]:
        if isinstance(s, dict):
            name = s.get("name") or s.get("title")
        else:
            name = s
        if name:
            out.append(str(name))
    return out[:12]


def _norm_harvestapi(p: dict, url: str) -> dict:
    pos = (p.get("currentPosition") or p.get("experience") or [{}])[0] or {}
    loc = (p.get("location") or {}).get("parsed") or {}
    return {
        "linkedin_url": p.get("linkedinUrl") or url,
        "first_name": p.get("firstName"),
        "last_name": p.get("lastName"),
        "title": pos.get("position") or p.get("headline"),
        "headline": p.get("headline"),
        "company_name": pos.get("companyName"),
        "company_linkedin": pos.get("companyLinkedinUrl"),
        "tenure": pos.get("duration"),
        "country": loc.get("countryCode") or (p.get("location") or {}).get("countryCode"),
        "location": loc.get("text") or (p.get("location") or {}).get("linkedinText"),
        "about": (p.get("about") or "")[:1200],
        "skills": _skills(p.get("topSkills") or p.get("skills")),
        "open_to_work": bool(p.get("openToWork")),
    }


def _norm_dev_fusion(p: dict, url: str) -> dict:
    """dev_fusion's shape, measured by scripts/probe.py on 2026-08-15.

    🔑 It carries a STRUCTURED `jobTitle` ("Chairman and CEO") alongside the
    self-written `headline` ("Chairman and CEO at Microsoft"). Same rule as the
    other actor: the structured field is the fact the seniority tier is derived
    from, the headline is fallback and colour for the draft. It also exposes
    `companyName` and `companyLinkedin` at the TOP level rather than inside a
    position array — reading them from the harvestapi path returns None, which
    would cost us the employer key and send the company step back to a search.
    """
    return {
        "linkedin_url": p.get("linkedinUrl") or p.get("linkedinPublicUrl") or url,
        "first_name": p.get("firstName"),
        "last_name": p.get("lastName"),
        "title": p.get("jobTitle") or p.get("headline"),
        "headline": p.get("headline"),
        "company_name": p.get("companyName"),
        "company_linkedin": p.get("companyLinkedin"),
        "tenure": p.get("currentJobDuration"),
        "country": p.get("addressCountryOnly"),
        "location": p.get("addressWithCountry") or p.get("jobLocation"),
        "about": (p.get("about") or "")[:1200],
        "skills": _skills(p.get("topSkillsByEndorsements") or p.get("skills")),
        "open_to_work": bool(p.get("isJobSeeker")),
    }


# ⚠️ THE OUTPUT SHAPE DIFFERS PER ACTOR, and getting it wrong fails as silently as
# getting the input key wrong did. dev_fusion returns none of harvestapi's
# `currentPosition[]` fields, so the harvestapi mapper applied to a dev_fusion item
# yields title-from-headline and a null company — a record that looks thin rather
# than mis-parsed, and scores as an honest unknown. Normalise per actor, and record
# WHICH actor produced the row so a shape change is traceable to a source.
_PERSON_NORMALISERS = {
    "dev_fusion~linkedin-profile-scraper": _norm_dev_fusion,
    "harvestapi~linkedin-profile-scraper": _norm_harvestapi,
}


def scrape_person(url: str, budget: Budget) -> dict:
    """Normalise a person record. Returns {} when nothing came back.

    Tries each actor in turn. A refusal from one (permission gate, plan cap) moves
    to the next; if EVERY actor refuses, `ActorRefused` propagates — because at that
    point the honest report is "we were blocked", not "this person has no profile".
    """
    items, refusals, used = [], [], None
    for actor, key in PERSON_ACTORS:
        try:
            items = apify_call(actor, {key: [url]}, budget, what=f"person: {url[-34:]}")
        except ActorRefused as exc:
            refusals.append(f"{actor.split('~')[0]}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 — a permission gate reads as Forbidden
            refusals.append(f"{actor.split('~')[0]}: {type(exc).__name__}: {str(exc)[:90]}")
            continue
        if items:
            used = actor
            break

    if not items:
        if refusals:
            raise ActorRefused(" | ".join(refusals))
        return {}

    norm = _PERSON_NORMALISERS.get(used, _norm_harvestapi)
    rec = norm(items[0], url)
    rec["source_actor"] = (used or "").split("~")[0] or None
    return rec


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

def enrich(lead: dict, budget: Budget, on_note=None) -> dict:
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
        # The trace is already the audit log of this lookup; streaming it out as it
        # is written means the UI can show the real stage it is on rather than a
        # progress bar animating against a guess.
        if on_note:
            on_note(msg)

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
        try:
            rec["person"] = scrape_person(found["url"], budget)
        except ActorRefused as exc:
            # ⚠️ NOT a fact about this lead. The scraper refused us — a plan limit,
            # a quota, a permission gate. Recording it as "no title found" would
            # turn our billing status into their seniority, so it is named here and
            # forced to a human downstream.
            note(f"SEAM: person scraper refused — {exc}")
            rec["blocked"] = f"person scraper refused: {exc}"
            rec["unknowns"].append("person_record")
        if rec["person"].get("source_actor"):
            # WHICH scraper answered, in the stored trace. Two actors with different
            # response shapes feed the same scorer, so when a field goes missing the
            # first question is which one produced the row — and the answer should not
            # require re-running the lookup to find out.
            note(f"person record from {rec['person']['source_actor']}")
        if not rec["person"] and not rec.get("blocked"):
            note("profile page returned nothing")
            rec["unknowns"].append("person_record")

    # --- 2. the company -----------------------------------------------------
    # Prefer the company URL off the person's current position: it is the employer
    # LinkedIn itself links them to, which is stronger than anything we could guess.
    target = rec["person"].get("company_linkedin")
    if not target:
        # No URL on the person record. A bare name ("personio") is a poor key —
        # the company actor returns nothing for it — so spend one search to turn
        # the name into a page URL before giving up on the lookup.
        hint = (rec["person"].get("company_name") or lead.get("company")
                or company_guess(domain))
        note(f"no company URL on the profile — searching for the page: {hint}")
        target = find_company_page(domain, hint, budget) or hint

    if target:
        note(f"company lookup: {target}")
        try:
            rec["company"] = scrape_company(target, budget)
        except ActorRefused as exc:
            note(f"SEAM: company scraper refused — {exc}")
            rec["blocked"] = f"company scraper refused: {exc}"
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
