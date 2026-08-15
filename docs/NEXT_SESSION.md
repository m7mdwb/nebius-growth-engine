# Kickoff prompt for the next session

Open the session **in this folder** (`Career/nebius-growth-engine`) so `CONTEXT.md`,
`README.md` and the git history are all in reach, then paste the block below.

---

## 📋 Paste this

```
Read CONTEXT.md first — it is the standing brief and it opens with the current
state and the one blocking action.

This is the Nebius Academy take-home, due Monday 17 Aug EOD. Track C (AEO) is the
submission, Track A (inbound leads) is the second tab. Both run against live APIs.
The scored artifact is a 5–8 minute Loom of it running, not a deck.

Before anything else:

1. Run `python scripts/probe.py`. It makes one call per integration and prints
   PASS/FAIL with the real data shape. Nothing gets built on an unverified
   adapter. If a probe fails twice it becomes a marked seam, not a debugging
   session — the deadline is closer than the fix.

2. Check whether the Apify dev_fusion approval has been granted. If probe 3 names
   dev_fusion as the actor used, it has; re-run the lead engine so the stored run
   has correct seniority and function points.

Then build: a `Track C · Logic` tab, mirroring the `Track A · Logic` tab that
already exists.

Copy the pattern from `flowChart()` in web/static/index.html — a vertical spine of
numbered stages, branch-offs to terminal states, every node carrying the count
from the last real run, and the left edge colour-coded by what KIND of step it is.
The Track A one is the reference for tone and density; do not invent a new visual
language for this one.

What Track C's flow actually is:

  config/queries.yaml (the measurement contract, hashed)
    → 10 buyer-intent queries + 2 branded controls, excluded from the count
    → per engine: Claude (web search) · Google AI Overviews (Apify)
      · ChatGPT and Perplexity are DECLARED SEAMS, no key
    → per query: repeats (a single sample is not a measurement)
    → classify each answer: cited / mentioned / absent / UNMEASURED
      · an errored or empty engine is unmeasured, never absent
    → benchmark: "we appear in N of 10", a count and never a percentage
    → for the queries we lost: classify every cited domain by source type
      (review platform / competitor-owned / analyst / community / editorial)
    → SEO↔AEO overlap, measured from the SERP that ships with the AI Overview
    → recommendations: the model writes, but only from that evidence table

Make the seams and the unmeasured cells visible in the diagram — "we did not
look" and "we looked and found nothing" being different states is the whole
argument of Track C, and a flowchart that hides it would undercut the tab it
sits next to.

Constraints that have not changed, all four load-bearing:
- Financials stay unknown, never guessed. Headcount + headcount growth is the
  growth proxy; everything else is an explicit unknown worth zero points.
- Scoring stays deterministic. The model infers pain points and writes; rules
  decide.
- Per-run cost caps on Apify and Serper. Apify is a $5/month FREE plan and is
  the binding constraint on the whole project.
- No scraped personal data in the committed repo or the exported HTML.

Cost: rehearse Track C with `--limit 3 --engine claude` (~$0.35, zero Apify).
A full run is ~$2.45 and 20 Apify calls. Check `db.run_cost()` after any run —
spend is measured now, not estimated.
```

---

## What is already done, so it doesn't get rebuilt

- **Both tracks run live.** 5/5 integrations verified; Anthropic topped up 15 Aug.
- **Track A covers all four brief bullets**, with real enrichment where the brief
  allowed mocked. Audit table is in `CONTEXT.md`.
- **`Track A · Logic`** live flowchart tab — the pattern to copy.
- **Cost is measured**, not estimated: `aeo/pricing.py` reads `response.usage`,
  stored per observation and per lead, running total printed during a run.
- **The cron is deliberately off** (`workflow_dispatch` only) with the arithmetic
  beside the commented `schedule:` line. That is a scope decision to defend in the
  Loom, not a gap — everything that makes runs comparable over time is built.
- **The export redacts** names, emails, profile URLs and drafts by default;
  verified with a leak check.
- **`aeo/analyze.py`**: benchmark, source gap, SEO overlap. **`aeo/recommend.py`**:
  evidence in, 3–5 recommendations out.

## Still open

1. **Approve dev_fusion on Apify** (a click) — then re-run the lead engine.
2. **`Track C · Logic` tab** — the task above.
3. **No GitHub remote yet.** The brief asks for a repo link. `gh repo create
   m7mdwb/nebius-growth-engine --private`, push, then confirm no secret ever
   entered history.
4. **Record the Loom.** Say three things out loud: Track C is the submission and
   Track A is the second tab (the brief says pick one and scores scope judgment);
   the cron is off on purpose and why; the behavioural signals are mocked while
   the firmographics are real.

## The two stories worth telling on camera

**The probe caught four faults on first contact**, and four of the five fail
*silently* — they return plausible output rather than an error. Claude answering
with zero parseable citations would have made citation share a flat 0% that reads
as a finding rather than a broken instrument.

**A scraper's plan limit was being laundered into a fact about a lead.** harvestapi
caps free accounts at 20 runs and, past that, *succeeds* with one dataset item:
`{"error": "Free users are limited to 20 runs"}`. Non-empty result, every field
mapped to `None`, lead scored as a person with "no job title found" — an honest
unknown, built out of our billing status. `cost.ActorRefused` catches it now. It is
the thesis of both tracks, caught in our own code.
