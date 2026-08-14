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

from .config import ROOT, env

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
# enrichment
# ---------------------------------------------------------------------------

# A stand-in for Clearbit / Apollo / ZoomInfo. The brief allows mocked
# enrichment and says to mark the seam, so this is the seam: one function, one
# return shape. Swapping in a real provider is this function and nothing else.
_FIXTURES: dict[str, dict] = {
    "meridianbank.com": {
        "company": "Meridian Bank", "industry": "Financial services",
        "headcount": 8200, "title": "Chief People Officer",
        "seniority": "exec", "function": "People",
    },
    "helioxenergy.com": {
        "company": "Heliox Energy", "industry": "Energy",
        "headcount": 3400, "title": "Head of Talent Development",
        "seniority": "leader", "function": "L&D",
    },
    "kestrel-logistics.com": {
        "company": "Kestrel Logistics", "industry": "Logistics",
        "headcount": 620, "title": "Learning & Development Manager",
        "seniority": "manager", "function": "L&D",
    },
    # voltaire-partners.fr is deliberately absent. See decision 3 in the docstring.
}


def domain_of(email: str) -> str:
    return email.split("@")[-1].strip().lower() if "@" in email else ""


def enrich(lead: dict) -> dict:
    """Look the lead up. Returns `enriched: False` when we simply do not know.

    The important line in this function is the last one. Returning zeros for an
    unknown company would let a real buyer fall through as a weak lead, and the
    failure would be invisible because a zero looks exactly like a low score.
    """
    d = domain_of(lead["email"])
    hit = _FIXTURES.get(d)
    if hit:
        return {**hit, "domain": d, "enriched": True}
    return {"domain": d, "enriched": False,
            "company": lead.get("company") or "", "industry": None,
            "headcount": None, "title": None, "seniority": None, "function": None}


# ---------------------------------------------------------------------------
# disqualification — before scoring, and absolute
# ---------------------------------------------------------------------------

def disqualify(lead: dict, enriched: dict, fit: FitDefinition) -> str | None:
    d = fit.disq
    domain = enriched.get("domain", "")

    if domain in {x.lower() for x in d.get("free_email_domains", [])}:
        return f"personal email domain ({domain}) — no company to sell a platform to"

    # Word-boundary matched — see _match(). A blocked role must be the word,
    # not a fragment of a longer one.
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


def score(lead: dict, enriched: dict, fit: FitDefinition) -> tuple[int, list[dict]]:
    """Return the total and every point that made it.

    The breakdown is not decoration. A score you cannot take apart is a score
    nobody will trust the first time it disagrees with a salesperson, and that
    is the moment these systems get switched off.
    """
    icp, rows, total = fit.icp, [], 0

    hc = enriched.get("headcount")
    if hc is not None:
        for b in icp["headcount"]["bands"]:
            if b["min"] <= hc <= b["max"]:
                total += b["points"]
                rows.append({"factor": "Headcount", "detail": f"{hc:,} employees", "points": b["points"]})
                break

    title = enriched.get("title") or ""
    for r in icp["seniority"]:
        if _match(title, r["match"]):
            total += r["points"]
            rows.append({"factor": "Seniority", "detail": f"{title} ({r['label']})", "points": r["points"]})
            break

    fn = f"{enriched.get('function') or ''} {title}"
    for r in icp["function"]:
        if _match(fn, r["match"]):
            total += r["points"]
            rows.append({"factor": "Function", "detail": r["label"], "points": r["points"]})
            break

    ind = enriched.get("industry") or ""
    for r in icp["industry"]:
        if _match(ind, r["match"]):
            total += r["points"]
            rows.append({"factor": "Industry", "detail": ind, "points": r["points"]})
            break

    by_signal = {r["signal"]: r["points"] for r in icp["intent"]}
    for sig in lead.get("signals", []):
        if sig in by_signal:
            total += by_signal[sig]
            rows.append({"factor": "Intent", "detail": sig.replace("_", " "), "points": by_signal[sig]})

    return total, rows


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
        "subject": {"type": "string"},
        "message": {"type": "string"},
        "facts_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Each specific fact from the lead record that this message leans on.",
        },
    },
    "required": ["subject", "message", "facts_used"],
    "additionalProperties": False,
}

_PROMPT = """You are writing the first outbound message to an inbound lead for Nebius \
Academy, which sells an enterprise AI learning platform: a customised, partly \
AI-delivered training environment, not a course catalogue.

Lead record:
{record}

Write a short first-touch email.

Rules:
- Open on something specific to THIS record. If they completed the AI readiness \
assessment, the result is the opening, not a greeting.
- No "I hope this email finds you well", no "I wanted to reach out", no "at {company} \
you're probably...". If the sentence would survive a find-and-replace of the name, \
delete it.
- Under 110 words. One question at the end, answerable in a sentence.
- Do not invent facts. Use only what is in the record.
- List in facts_used every specific fact the message actually leans on. If that \
list would be empty, the message is a mail-merge and you should rewrite it."""


def draft(lead: dict, enriched: dict, breakdown: list[dict], routing: dict,
          fit: FitDefinition) -> dict:
    key = env("ANTHROPIC_API_KEY")
    if not key:
        return {"error": "SEAM: no ANTHROPIC_API_KEY — drafting skipped, "
                         "enrichment, scoring and routing all ran"}

    import anthropic

    record = {
        "name": f"{lead.get('first_name','')} {lead.get('last_name','')}".strip(),
        "company": enriched.get("company") or lead.get("company"),
        "title": enriched.get("title"),
        "industry": enriched.get("industry"),
        "headcount": enriched.get("headcount"),
        "how_they_arrived": lead.get("source"),
        "behaviour": lead.get("signals"),
        "form_notes": lead.get("note"),
        "why_they_scored": [f"{r['factor']}: {r['detail']}" for r in breakdown],
        "routed_to": routing["route"],
    }

    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.messages.create(
            model=fit.drafting.get("model", "claude-opus-5"),
            max_tokens=int(fit.drafting.get("max_tokens", 900)),
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": _PROMPT.format(
                record=json.dumps(record, indent=2, ensure_ascii=False),
                company=record["company"] or "their company",
            )}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}

    if getattr(resp, "stop_reason", None) == "refusal":
        return {"error": "refused by safety classifier"}

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "draft was not valid JSON", "raw": text[:400]}


# ---------------------------------------------------------------------------
# the pipeline
# ---------------------------------------------------------------------------

def process(lead: dict, fit: FitDefinition) -> dict:
    enriched = enrich(lead)
    name = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()
    base = {
        "email": lead["email"], "name": name, "source": lead.get("source"),
        "company": enriched.get("company") or lead.get("company") or "",
        "domain": enriched.get("domain"), "enriched": 1 if enriched["enriched"] else 0,
        "industry": enriched.get("industry"), "headcount": enriched.get("headcount"),
        "seniority": enriched.get("seniority"), "job_function": enriched.get("function"),
        "title": enriched.get("title"),
    }

    reason = disqualify(lead, enriched, fit)
    if reason:
        return {**base, "score": None, "breakdown": [], "route": "disqualified",
                "sla_minutes": None, "disqualified": reason,
                "message": None, "evidence": [], "error": None,
                "route_why": "Disqualifiers are checked before scoring and are absolute — "
                             "a strong profile must never outvote a hard exclusion."}

    if not enriched["enriched"]:
        # Not a low score. We did not manage to look this one up, and a lead we
        # know nothing about is a question for a human, not a number.
        return {**base, "score": None, "breakdown": [], "route": UNENRICHED,
                "sla_minutes": 240, "disqualified": None,
                "message": None, "evidence": [], "error": None,
                "route_why": "Enrichment returned nothing for this domain. Scoring it "
                             "would invent a low number out of missing data and bin a "
                             "lead that booked a demo — so it goes to a human instead."}

    total, breakdown = score(lead, enriched, fit)
    routing = route(total, breakdown, fit)
    out = {**base, "score": total, "breakdown": breakdown, "route": routing["route"],
           "sla_minutes": routing.get("sla_minutes"), "disqualified": None,
           "route_why": routing.get("why"), "error": None}

    d = draft(lead, enriched, breakdown, routing, fit)
    out["message"] = None if d.get("error") else f"{d.get('subject','')}\n\n{d.get('message','')}".strip()
    out["evidence"] = d.get("facts_used", [])
    out["error"] = d.get("error")
    return out


def collect(fit: FitDefinition | None = None, on_progress=None) -> int:
    """Run every sample lead through the pipeline and store the result."""
    from . import db

    fit = fit or load_fit()
    say = on_progress or (lambda _ev: None)
    samples = fit.samples

    with db.session() as conn:
        run_id = db.start_lead_run(conn, fit_hash=fit.fit_hash)
        say({"event": "run_started", "run_id": run_id, "steps": len(samples)})

        for i, lead in enumerate(samples, 1):
            say({"event": "step", "step": i, "steps": len(samples), "email": lead["email"]})
            row = process(lead, fit)
            db.record_lead(conn, run_id, row)
            conn.commit()   # same reason as the AEO collector: survive an interruption
            say({"event": "result", "step": i, "steps": len(samples),
                 "email": lead["email"], "route": row["route"], "score": row.get("score"),
                 "drafted": bool(row.get("message"))})

        db.finish_lead_run(conn, run_id)

    say({"event": "run_finished", "run_id": run_id})
    return run_id


def summarise(rows: list[dict]) -> dict:
    """Counts the demo needs, plus the two that make the design legible."""
    from collections import Counter
    routes = Counter(r["route"] for r in rows)
    scored = [r for r in rows if r.get("score") is not None]
    drafted = [r for r in rows if r.get("message")]
    return {
        "total": len(rows),
        "routes": dict(routes),
        "scored": len(scored),
        "avg_score": round(sum(r["score"] for r in scored) / len(scored), 1) if scored else 0,
        "disqualified": sum(1 for r in rows if r["route"] == "disqualified"),
        "needs_review": sum(1 for r in rows if r["route"] == UNENRICHED),
        "drafted": len(drafted),
        # A draft that leans on no specific fact is a mail-merge. Counting them
        # is the only way "personalised" stays a claim you can check.
        "generic_drafts": sum(1 for r in drafted if not r.get("evidence")),
    }
