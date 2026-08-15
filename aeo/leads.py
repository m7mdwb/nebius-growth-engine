"""Track A — inbound lead engine.

A raw form fill goes in; an enriched, scored, routed lead with a drafted first
touch comes out. Same philosophy as the AEO side, applied to a different problem.

Four decisions, each of which is the thing that breaks these systems in
production when it goes the other way:

1. RULES DECIDE, THE MODEL WRITES. Scoring is arithmetic over a config file.
   Ask an LLM to "score this lead out of 100" and it returns a confident number
   it cannot reproduce twice and nobody can audit. The model's job is the one
   thing rules genuinely cannot do — write a sentence that sounds like a person.

2. DISQUALIFIERS RUN BEFORE SCORING, AND THEY ARE ABSOLUTE. A strong
   firmographic profile must never outvote "student, personal email". Scoring
   a disqualified lead and letting it win on points is the commonest way one
   of these quietly poisons a pipeline.

3. UNENRICHABLE IS NOT LOW-SCORING. A lead we could not look up gets routed to
   human review, not to the bottom of the list. "We don't know" and "we know
   it's weak" are different states — the same distinction the AEO side makes
   between a seam and an absence, and it matters more here because this one
   silently bins real buyers.

4. THE DRAFT MUST CITE ITS EVIDENCE. The model returns which enrichment facts
   it used. A draft that cites nothing is a mail-merge in costume, and now you
   can see that at a glance instead of taking it on trust.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import enrich as _enrich
from .config import ROOT, env
from .cost import Budget, BudgetExhausted

LEADS_CONFIG = ROOT / "config" / "leads.yaml"

UNENRICHED = "needs_review"


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@dataclass
class FitDefinition:
    raw: dict

    @property
    def icp(self) -> dict: return self.raw["icp"]

    @property
    def disq(self) -> dict: return self.raw["disqualifiers"]

    @property
    def routing(self) -> list[dict]: return self.raw["routing"]

    @property
    def drafting(self) -> dict: return self.raw.get("drafting", {})

    @property
    def samples(self) -> list[dict]: return self.raw.get("samples", [])

    @property
    def enrichment(self) -> dict: return self.raw.get("enrichment", {})

    @property
    def never_guessed(self) -> list[str]: return list(self.raw.get("never_guessed", []))

    def budget(self) -> Budget:
        """A fresh spend cap per run, read from the config.

        Deliberately per-run and not a module global: a web request must never inherit
        the spend of the request before it, or the fifth lead someone types gets
        refused for reasons belonging to the first.
        """
        from decimal import Decimal
        caps = self.enrichment.get("caps") or {}
        return Budget(
            apify_calls=int(caps.get("apify_calls", 12)),
            serper_calls=int(caps.get("serper_calls", 8)),
            apify_usd_per_call=Decimal(str(caps.get("apify_usd_per_call", "0.10"))),
        )

    def method(self) -> dict:
        """Everything needed to explain the design, straight from the config.

        Rendered in the UI rather than written up separately, so the explanation
        cannot drift from the rules it is explaining — the commonest way a scoring
        model ends up documented as something it no longer is.
        """
        return {"icp": self.icp, "disqualifiers": self.disq,
                "routing": self.routing, "enrichment": self.enrichment,
                "fit_hash": self.fit_hash}

    @property
    def fit_hash(self) -> str:
        """Fingerprint of the qualification policy.

        A score is only comparable to another score produced under the same
        definition. Stamping the hash on the run means a changed policy is
        visible instead of showing up as a mysterious shift in lead quality.
        """
        blob = json.dumps({"icp": self.icp, "disq": self.disq, "routing": self.routing},
                          sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]


def load_fit(path: Path | None = None) -> FitDefinition:
    return FitDefinition(yaml.safe_load((path or LEADS_CONFIG).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# enrichment — REAL, as of 2026-08-15. See aeo/enrich.py.
# ---------------------------------------------------------------------------
#
# This used to be a five-row fixture dict. It is now a live waterfall: Serper finds
# the LinkedIn profile behind the name and email, two Apify actors read the person and
# the company, and the record is reconciled against the email domain before anything
# is scored. `enrich.py` holds the lookups; this file flattens the result into the
# shape the scorer already expected, so the scoring rules below did not have to change
# to accommodate real data — which is the test of whether they were written properly.

domain_of = _enrich.domain_of


def seniority_of(title: str, fit: FitDefinition) -> tuple[str | None, int]:
    """Derive seniority from the title BY OUR RULES.

    Never imported from a provider's own `seniority` field, however convenient — every
    vendor's taxonomy differs, so importing one means our score silently changes
    meaning the day we switch vendor. The title is the raw fact; the tier is our
    judgement, and it is versioned in leads.yaml where sales can argue with it.
    """
    for r in fit.icp["seniority"]:
        if _match(title or "", r["match"]):
            return r["label"], r["points"]
    return None, 0


def function_of(title: str, fit: FitDefinition) -> tuple[str | None, int]:
    for r in fit.icp["function"]:
        if _match(title or "", r["match"]):
            return r["label"], r["points"]
    return None, 0


def flatten(rec: dict, fit: FitDefinition) -> dict:
    """The live enrichment record -> the flat shape the scorer reads."""
    p, c = rec.get("person") or {}, rec.get("company") or {}
    title = p.get("title") or ""
    sen, _ = seniority_of(title, fit)
    fn, _ = function_of(f"{title} {p.get('headline') or ''}", fit)
    return {
        "domain": rec.get("domain"),
        "company": c.get("name") or rec.get("company_typed") or "",
        "industry": c.get("industry"),
        "headcount": c.get("headcount"),
        "headcount_band": c.get("headcount_band"),
        "title": title or None,
        "headline": p.get("headline"),
        "seniority": sen,
        "function": fn,
        "linkedin_url": p.get("linkedin_url"),
        "company_linkedin": c.get("linkedin_url"),
        "website": c.get("website"),
        "hq": c.get("hq"),
        "tenure": p.get("tenure"),
        "about": p.get("about"),
        "company_description": c.get("description"),
        "specialities": c.get("specialities"),
        "enriched": rec.get("enriched", False),
        "unknowns": rec.get("unknowns", []),
        "never_guessed": rec.get("never_guessed", []),
        "reconciliation": rec.get("reconciliation") or {},
        "trace": rec.get("trace", []),
    }


def growth(conn, domain: str, headcount: int | None, name: str | None,
           fit: FitDefinition) -> dict:
    """Record what we see now; report growth only if we saw it before.

    Returns {known, pct, label, points, detail}. `known: False` is the normal case on
    first contact and is NOT a failure — it is the correct answer to a question that
    needs two observations. It scores zero, and the UI must say "not yet measured"
    rather than drawing a 0% that reads as flat.
    """
    from . import db

    cfg = fit.icp.get("headcount_growth") or {}
    min_days = int(cfg.get("min_days", 7))

    prior = db.prior_snapshot(conn, domain, min_days) if domain else None
    if headcount is not None and domain:
        db.record_snapshot(conn, domain=domain, headcount=headcount, company_name=name)

    if not prior or headcount is None or not prior.get("headcount"):
        return {"known": False, "pct": None, "label": None, "points": 0,
                "detail": f"first sighting of {domain or 'this company'} — growth needs a "
                          f"second reading at least {min_days} days later. LinkedIn "
                          f"publishes no history, so this cannot be looked up, only measured."}

    before = int(prior["headcount"])
    pct = round(100.0 * (headcount - before) / before, 1) if before else 0.0
    # A comparison against a SEEDED prior reading is not a measurement, and the flag
    # travels with the number rather than living in a caption next to it. Same rule as
    # runs.is_synthetic: a chart must not be able to render invented history as real.
    synthetic = prior.get("source") == "synthetic-backfill"
    detail = f"{before:,} → {headcount:,} since {prior['observed_at'][:10]}"
    if synthetic:
        detail += "  ⚠ baseline is SEEDED, not measured"

    for band in cfg.get("bands", []):
        if pct >= float(band["min_pct"]):
            return {"known": True, "pct": pct, "label": band["label"],
                    "points": int(band["points"]), "synthetic": synthetic,
                    "detail": detail}
    return {"known": True, "pct": pct, "label": "shrinking", "points": 0,
            "synthetic": synthetic, "detail": detail}


# ---------------------------------------------------------------------------
# disqualification — before scoring, and absolute
# ---------------------------------------------------------------------------

def disqualify(lead: dict, enriched: dict, fit: FitDefinition) -> str | None:
    d = fit.disq
    domain = enriched.get("domain", "")

    # ⚠️ The UNION of both lists, deliberately. `enrich.FREE_MAIL` is the list that
    # decides whether to spend two paid calls; this one decides whether the lead is
    # disqualified. They had drifted — gmx.de and web.de were in the first and not the
    # second, so a German personal address skipped enrichment (correctly) and then
    # routed `needs_review` instead of `disqualified`, because with nothing looked up
    # there was nothing left to disqualify it on. The wrong branch, for a reason
    # invisible from either file on its own.
    free = {x.lower() for x in d.get("free_email_domains", [])} | _enrich.FREE_MAIL
    if domain in free:
        return f"personal email domain ({domain}) — no company to sell a platform to"

    # Word-boundary matched — see _match(). A blocked role must be the word,
    # not a fragment of a longer one.
    #
    # ⚠️ The LinkedIn `headline` is deliberately NOT in this blob. It is self-written
    # marketing and routinely contains words like "student of the craft" or "intern
    # programme lead", which would disqualify real buyers on a phrase they chose for
    # flattery. The structured title and the form note are the checkable facts.
    blob = " ".join(str(x or "") for x in
                    (lead.get("note"), enriched.get("title"), lead.get("company")))
    for role in d.get("blocked_roles", []):
        if _match(blob, [role]):
            return f"role signal '{role}' — not a buyer"

    ind = enriched.get("industry") or ""
    for bad in d.get("blocked_industries", []):
        if bad and _match(ind, [bad]):
            return f"industry '{enriched['industry']}' is excluded"

    hc = enriched.get("headcount")
    if hc is not None and hc < int(d.get("min_headcount", 0)):
        return f"{hc} employees — below the {d['min_headcount']} floor"

    return None


# ---------------------------------------------------------------------------
# scoring — deterministic, and it shows its working
# ---------------------------------------------------------------------------

def _match(text: str, terms: list[str]) -> bool:
    """Word-boundary match, never a substring.

    ⚠️ This is not a style preference. A plain `term in text` disqualified a real
    L&D Manager on the blocked role "intern", because her form note said the
    company had "no INTERNal training capability". Same class of bug bins
    "director" inside "redirector" and "lead" inside "leadership".

    The failure is nasty because it is silent and it fails toward rejection:
    the lead simply never appears, and nobody goes looking for the ones that
    didn't arrive.
    """
    t = (text or "").lower()
    for term in terms:
        term = term.lower().strip()
        if not term:
            continue
        left = r"\b" if term[:1].isalnum() else ""
        right = r"\b" if term[-1:].isalnum() else ""
        if re.search(f"{left}{re.escape(term)}{right}", t):
            return True
    return False


def score(lead: dict, enriched: dict, fit: FitDefinition,
          growth_info: dict | None = None) -> tuple[int, list[dict], list[dict]]:
    """Return the total, every point that made it, and everything we could not score.

    The breakdown is not decoration. A score you cannot take apart is a score
    nobody will trust the first time it disagrees with a salesperson, and that
    is the moment these systems get switched off.

    🔑 The THIRD return value is the one that makes this honest. A factor we could not
    measure is listed in `gaps`, not scored as zero and not silently dropped. Those are
    different claims: "we looked and this company is not growing" versus "we have never
    looked". A dashboard that renders both as a missing row teaches the reader to treat
    absence as a negative finding, which is the error the whole repo is built against.
    """
    icp, rows, gaps, total = fit.icp, [], [], 0

    def gap(factor: str, why: str) -> None:
        gaps.append({"factor": factor, "why": why, "points": 0})

    hc = enriched.get("headcount")
    if hc is None:
        gap("Headcount", "no company record — not scored as zero")
    else:
        for b in icp["headcount"]["bands"]:
            if b["min"] <= hc <= b["max"]:
                total += b["points"]
                rows.append({"factor": "Headcount", "detail": f"{hc:,} employees",
                             "points": b["points"]})
                break
        else:
            gap("Headcount", f"{hc:,} employees falls outside every band")

    # The growth proxy. Zero points when unknown, and named as unknown.
    g = growth_info or {}
    if g.get("known"):
        total += g["points"]
        rows.append({"factor": "Headcount growth",
                     "detail": f"{g['pct']:+.1f}% — {g['label']} ({g['detail']})",
                     "points": g["points"]})
    else:
        gap("Headcount growth", g.get("detail") or "needs a second sighting")

    title = enriched.get("title") or ""
    if not title:
        gap("Seniority", "no job title found")
    else:
        label, pts = seniority_of(title, fit)
        if label:
            total += pts
            rows.append({"factor": "Seniority", "detail": f"{title} ({label})", "points": pts})
        else:
            gap("Seniority", f"'{title}' matches no seniority rule")

    # ⚠️ Match on the RAW FACTS only — the title and the headline. `enriched["function"]`
    # is a label this codebase already derived from those same two fields, and feeding a
    # derived label back in as text to match against means renaming a label could silently
    # change a score. It is idempotent today; it is a trap the first time somebody edits
    # a label in leads.yaml to read more nicely on screen.
    label, pts = function_of(f"{title} {enriched.get('headline') or ''}", fit)
    if label:
        total += pts
        rows.append({"factor": "Function", "detail": label, "points": pts})
    else:
        gap("Function", "the title maps to no target function")

    ind = enriched.get("industry") or ""
    if not ind:
        gap("Industry", "no industry on the company page")
    else:
        for r in icp["industry"]:
            if _match(ind, r["match"]):
                total += r["points"]
                rows.append({"factor": "Industry", "detail": ind, "points": r["points"]})
                break
        else:
            gap("Industry", f"'{ind}' is outside the target industries")

    by_signal = {r["signal"]: r["points"] for r in icp["intent"]}
    signals = lead.get("signals") or []
    if not signals:
        # A cold lookup. Worth saying out loud, because it is why this lead cannot
        # route hot no matter how good the firmographics are.
        gap("Intent", "no first-party behaviour on this record — a cold lookup "
                      "cannot clear the intent gate, by design")
    for sig in signals:
        if sig in by_signal:
            total += by_signal[sig]
            rows.append({"factor": "Intent", "detail": sig.replace("_", " "),
                         "points": by_signal[sig]})

    # Constraint 1, surfaced in the score itself rather than only in a config comment.
    for f in enriched.get("never_guessed", []):
        gap(f.replace("_", " ").title(),
            "not obtainable for a private company and never estimated — "
            "a model asked for this returns an invented number")

    return total, rows, gaps


def intent_points(breakdown: list[dict]) -> int:
    return sum(r["points"] for r in breakdown if r["factor"] == "Intent")


def route(total: int, breakdown: list[dict], fit: FitDefinition) -> dict:
    """Fit and intent are separate gates, and both must clear.

    ⚠️ The first version of this routed on the total alone, and sent a lead who
    registered for a webinar and never showed up straight to sales with a
    five-minute SLA — purely on headcount, seniority and industry. A big company
    with the right job title is not a buying signal, and a total that lets
    firmographics stand in for intent is how sales teams learn to ignore the
    lead queue.
    """
    intent = intent_points(breakdown)
    for rule in sorted(fit.routing, key=lambda r: -r["min_score"]):
        if total < rule["min_score"]:
            continue
        need = rule.get("min_intent")
        if need is not None and intent < need:
            continue          # fits the profile, hasn't done anything — keep looking
        return rule
    return fit.routing[-1]


# ---------------------------------------------------------------------------
# drafting — the one job rules cannot do
# ---------------------------------------------------------------------------

_SCHEMA = {
    "type": "object",
    "properties": {
        "pain_points": {
            "type": "array",
            # ⚠️ NOT `maxItems`. The structured-output schema rejects it outright:
            # "For 'array' type, property 'maxItems' is not supported". The cap is
            # stated in the prompt instead. Caught by a live run, not by the probe —
            # probe 5 had passed against the schema as it stood before pain points
            # were added, which is a fair reminder that a probe covers the call it
            # made, not the call you make next.
            "items": {
                "type": "object",
                "properties": {
                    "pain": {"type": "string",
                             "description": "The AI-adoption problem this company probably has."},
                    "evidence": {"type": "string",
                                 "description": "The fact IN THE RECORD that supports it."},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["pain", "evidence", "confidence"],
                "additionalProperties": False,
            },
        },
        "subject": {"type": "string"},
        "message": {"type": "string"},
        "facts_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Each specific fact from the lead record that this message leans on.",
        },
    },
    "required": ["pain_points", "subject", "message", "facts_used"],
    "additionalProperties": False,
}

_PROMPT = """You are writing the first outbound message to an inbound lead for Nebius \
Academy, which sells an enterprise AI learning platform: a customised, partly \
AI-delivered training environment with human instructors and instructional designers, \
sold per-client as a solution. It is not a course catalogue.

Lead record — every field here was either submitted by the lead or read from public \
company pages:
{record}

Do two things.

FIRST, infer up to {max_pain} pain points: what this specific organisation's \
AI-adoption problem probably is, and what this person's role would feel of it. \
Reason from the size, the industry, what the company says it does, and the seniority \
and function of the contact. A 200-person logistics firm and a 200,000-person bank \
have different problems, and a CHRO and a Head of Data feel the same problem \
differently.
- Each pain point must name the record field it is reasoning from, in `evidence`.
- Mark `confidence` honestly. "Large regulated enterprise, so probably has a \
governance bottleneck" is medium at best. Do not launder a guess as high confidence.
- If the record is too thin to infer anything, return fewer. An empty list is a \
legitimate answer and is better than three inventions.

SECOND, write the first-touch email, using the strongest pain point.

Rules for the email:
- Open on something specific to THIS record. If they completed the AI readiness \
assessment, the result is the opening, not a greeting.
- No "I hope this email finds you well", no "I wanted to reach out", no "at {company} \
you're probably...". If the sentence would survive a find-and-replace of the name, \
delete it.
- Under 110 words. One question at the end, answerable in a sentence.
- ⚠️ Do not invent facts. Use only what is in the record. In particular: you have NOT \
been given revenue, valuation or funding, and those are deliberately absent because \
they are not obtainable — do not refer to them, estimate them, or imply you know them.
- Present an inference as an inference. "I'd guess" is honest; stating it as a known \
fact about their business is not, and they will know.
- List in facts_used every specific fact the message actually leans on. If that \
list would be empty, the message is a mail-merge and you should rewrite it."""


def draft(lead: dict, enriched: dict, breakdown: list[dict], routing: dict,
          fit: FitDefinition, gaps: list[dict] | None = None) -> dict:
    key = env("ANTHROPIC_API_KEY")
    if not key:
        return {"error": "SEAM: no ANTHROPIC_API_KEY — drafting skipped, "
                         "enrichment, scoring and routing all ran"}

    import anthropic

    record = {
        "name": f"{lead.get('first_name','')} {lead.get('last_name','')}".strip(),
        "company": enriched.get("company") or lead.get("company"),
        "title": enriched.get("title"),
        "linkedin_headline": enriched.get("headline"),
        "tenure_in_role": enriched.get("tenure"),
        "industry": enriched.get("industry"),
        "headcount": enriched.get("headcount"),
        "headquarters": enriched.get("hq"),
        # The company's own words about itself. This is the richest input to a pain
        # point that is about THEM rather than about companies of their size.
        "company_describes_itself_as": enriched.get("company_description"),
        "company_specialities": enriched.get("specialities"),
        "how_they_arrived": lead.get("source"),
        "behaviour": lead.get("signals"),
        "form_notes": lead.get("note"),
        "why_they_scored": [f"{r['factor']}: {r['detail']}" for r in breakdown],
        # Named gaps go IN the prompt. A model that cannot see what is missing will
        # cheerfully fill it in; one that is told "headcount growth: not yet measured"
        # has no reason to invent a trend.
        "what_we_do_not_know": [f"{g['factor']}: {g['why']}" for g in (gaps or [])],
        "routed_to": routing["route"],
    }

    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.messages.create(
            model=fit.drafting.get("model", "claude-opus-5"),
            max_tokens=int(fit.drafting.get("max_tokens", 1200)),
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": _PROMPT.format(
                record=json.dumps(record, indent=2, ensure_ascii=False),
                company=record["company"] or "their company",
                max_pain=int(fit.drafting.get("max_pain_points", 3)),
            )}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}

    if getattr(resp, "stop_reason", None) == "refusal":
        return {"error": "refused by safety classifier"}

    # ⚠️ Check truncation BEFORE parsing. A response cut off at max_tokens is invalid
    # JSON, so the naive path reports "draft was not valid JSON" — which sends whoever
    # reads it hunting for a schema bug that does not exist. Measured: SAP's draft
    # failed exactly this way at 1,200 tokens, because four pain points with evidence
    # plus a message does not fit. Say which failure it actually was.
    if getattr(resp, "stop_reason", None) == "max_tokens":
        return {"error": "draft hit max_tokens and was truncated — raise "
                         "drafting.max_tokens in config/leads.yaml"}

    from . import pricing
    usage = pricing.usage_of(resp)

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        return {"error": "draft was not valid JSON", "raw": text[:400],
                "cost_usd": pricing.cost_usd(usage)}
    out["cost_usd"] = pricing.cost_usd(usage)
    return out


# ---------------------------------------------------------------------------
# the pipeline
# ---------------------------------------------------------------------------

def process(lead: dict, fit: FitDefinition, budget: Budget, conn) -> dict:
    """One lead, end to end. `conn` is needed for the headcount snapshots.

    The ORDER of the gates is the design, and it is deliberate:

        disqualify  ->  reconcile  ->  score  ->  route  ->  draft

    Disqualification first, because it is absolute and free. Reconciliation second,
    because a record that might belong to a different human must never reach the
    scorer — the whole point is that a wrong record scores *well*, not badly.
    """
    rec = _enrich.enrich(lead, budget)
    enriched = flatten(rec, fit)
    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()

    base = {
        "email": lead["email"], "name": name, "source": lead.get("source"),
        "company": enriched.get("company") or lead.get("company") or "",
        "domain": enriched.get("domain"), "enriched": 1 if enriched["enriched"] else 0,
        "industry": enriched.get("industry"), "headcount": enriched.get("headcount"),
        "seniority": enriched.get("seniority"), "job_function": enriched.get("function"),
        "title": enriched.get("title"), "linkedin_url": enriched.get("linkedin_url"),
        "reconciliation": enriched.get("reconciliation"),
        "unknowns": enriched.get("unknowns"), "trace": enriched.get("trace"),
        "gaps": [], "pain_points": [],
    }

    def stop(route: str, why: str, *, sla: int | None = None, dq: str | None = None) -> dict:
        return {**base, "score": None, "breakdown": [], "route": route,
                "sla_minutes": sla, "disqualified": dq, "message": None,
                "evidence": [], "error": None, "route_why": why,
                "headcount_growth": None}

    # --- 1. disqualifiers, absolute and before anything else ----------------
    reason = disqualify(lead, enriched, fit)
    if reason:
        return stop("disqualified",
                    "Disqualifiers are checked before scoring and are absolute — "
                    "a strong profile must never outvote a hard exclusion.", dq=reason)

    # --- 2. reconciliation --------------------------------------------------
    verdict = (enriched.get("reconciliation") or {}).get("verdict")
    if verdict == "mismatch":
        # 🔑 The most important branch in this file. We found A record; we cannot show
        # that it is THIS person's. Scoring it would not produce a low number — it
        # would produce a plausible, well-formed, completely wrong one, attached to a
        # real name, and every human downstream would trust it.
        return stop(UNENRICHED,
                    "A profile was found but it does NOT reconcile with the email "
                    "domain — "
                    f"{(enriched['reconciliation'] or {}).get('detail','')}. "
                    "This is most likely a different person with the same name. An "
                    "unreconciled record is not a weak lead, it is a wrong one, so it "
                    "goes to a human rather than to the scorer.", sla=240)

    # ⚠️ A REFUSED SCRAPER IS NOT A WEAK LEAD. Checked before the generic
    # unenrichable branch so the reason survives: "our Apify plan ran out of runs"
    # and "this person could not be found" produce identical-looking empty records,
    # and only one of them is a fact about the lead. Conflating them would let a
    # billing problem be recorded as a person's seniority.
    if rec.get("blocked"):
        return stop(UNENRICHED,
                    f"SEAM — {rec['blocked']}. This is a fact about our tooling, not "
                    "about this lead: the scraper refused before it ever looked. "
                    "Nothing here is evidence of anything, so it goes to a human and "
                    "is re-run once the block clears.", sla=240)

    if not enriched["enriched"]:
        # Not a low score. We did not manage to look this one up, and a lead we
        # know nothing about is a question for a human, not a number.
        return stop(UNENRICHED,
                    "Enrichment returned nothing usable for this domain. Scoring it "
                    "would invent a low number out of missing data and bin a lead who "
                    "completed the assessment — so it goes to a human instead.", sla=240)

    # --- 3. the growth proxy, measured rather than fetched ------------------
    g = growth(conn, enriched.get("domain") or "", enriched.get("headcount"),
               enriched.get("company"), fit)

    # --- 4. score, route ----------------------------------------------------
    total, breakdown, gaps = score(lead, enriched, fit, g)
    routing = route(total, breakdown, fit)
    out = {**base, "score": total, "breakdown": breakdown, "gaps": gaps,
           "route": routing["route"], "sla_minutes": routing.get("sla_minutes"),
           "disqualified": None, "route_why": routing.get("why"), "error": None,
           "headcount_growth": (f"{g['pct']:+.1f}% ({g['label']})" if g.get("known") else None)}

    # --- 5. the two things rules cannot do ---------------------------------
    d = draft(lead, enriched, breakdown, routing, fit, gaps)
    out["message"] = None if d.get("error") else \
        f"{d.get('subject','')}\n\n{d.get('message','')}".strip()
    out["evidence"] = d.get("facts_used", [])
    out["pain_points"] = d.get("pain_points", [])
    out["error"] = d.get("error")
    out["cost_usd"] = d.get("cost_usd")
    return out


def collect(fit: FitDefinition | None = None, on_progress=None,
            samples: list[dict] | None = None) -> int:
    """Run leads through the pipeline and store the results.

    `samples` overrides the config list, which is how the web form submits a single
    lead through the identical code path — the form is not a second implementation.
    """
    from . import db

    fit = fit or load_fit()
    say = on_progress or (lambda _ev: None)
    rows = samples if samples is not None else fit.samples
    budget = fit.budget()

    with db.session() as conn:
        run_id = db.start_lead_run(conn, fit_hash=fit.fit_hash)
        say({"event": "run_started", "run_id": run_id, "steps": len(rows)})

        for i, lead in enumerate(rows, 1):
            say({"event": "step", "step": i, "steps": len(rows), "email": lead["email"]})
            try:
                row = process(lead, fit, budget, conn)
            except BudgetExhausted as exc:
                # ⚠️ Reported, never swallowed. A run that quietly processes four of
                # five leads looks exactly like a run with four leads in it, and the
                # missing one is invisible — which is the same seam-versus-absence
                # error the AEO side is built to avoid, with money attached.
                row = {"email": lead["email"],
                       "name": f"{lead.get('first_name','')} {lead.get('last_name','')}".strip(),
                       "route": "capped", "score": None, "breakdown": [], "evidence": [],
                       "sla_minutes": None, "disqualified": None, "message": None,
                       "error": str(exc), "enriched": 0,
                       "route_why": "This run hit its per-run spend cap before reaching "
                                    "this lead. Not a verdict on the lead — raise the cap "
                                    "in config/leads.yaml and re-run."}
                db.record_lead(conn, run_id, row)
                conn.commit()
                say({"event": "result", "step": i, "steps": len(rows), "email": lead["email"],
                     "route": "capped", "score": None, "drafted": False})
                continue

            db.record_lead(conn, run_id, row)
            conn.commit()   # same reason as the AEO collector: survive an interruption
            say({"event": "result", "step": i, "steps": len(rows),
                 "email": lead["email"], "route": row["route"], "score": row.get("score"),
                 "drafted": bool(row.get("message"))})

        db.finish_lead_run(conn, run_id, notes=json.dumps(budget.summary()))

    say({"event": "run_finished", "run_id": run_id, "budget": budget.summary()})
    return run_id


def summarise(rows: list[dict]) -> dict:
    """Counts the demo needs, plus the ones that make the design legible."""
    from collections import Counter
    routes = Counter(r["route"] for r in rows)
    scored = [r for r in rows if r.get("score") is not None]
    drafted = [r for r in rows if r.get("message")]
    recon = Counter((r.get("reconciliation") or {}).get("verdict") or "n/a" for r in rows)
    return {
        "total": len(rows),
        "routes": dict(routes),
        "scored": len(scored),
        "avg_score": round(sum(r["score"] for r in scored) / len(scored), 1) if scored else 0,
        "disqualified": sum(1 for r in rows if r["route"] == "disqualified"),
        "needs_review": sum(1 for r in rows if r["route"] == UNENRICHED),
        "capped": sum(1 for r in rows if r["route"] == "capped"),
        "drafted": len(drafted),
        # A draft that leans on no specific fact is a mail-merge. Counting them
        # is the only way "personalised" stays a claim you can check.
        "generic_drafts": sum(1 for r in drafted if not r.get("evidence")),
        "reconciliation": dict(recon),
        # Measured, not estimated — see aeo/pricing.py. Anthropic only; the Serper
        # and Apify spend for the same run is in the budget summary, which is a
        # different provider and a different bill.
        "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4),
        # How many leads had a factor we could not measure. Surfaced because the
        # alternative is that gaps quietly become zeroes and nobody notices.
        "with_gaps": sum(1 for r in rows if r.get("gaps")),
        "growth_measured": sum(1 for r in rows if r.get("headcount_growth")),
    }
