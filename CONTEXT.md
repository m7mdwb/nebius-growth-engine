# CONTEXT — Nebius Academy take-home

Read this before touching anything. It is the standing brief for this repo: what
is being built, for whom, by when, and the four rules that are not negotiable.

---

## The assignment

**Growth Marketing Engineer (B2B), Nebius Academy.** Full brief in
[docs/assignment_brief.md](docs/assignment_brief.md).

**Due: Monday 17 August 2026, end of day.**

The brief asks for a working prototype on one of three tracks, capped at ~4 hours
(5 max), and is explicit about what it scores:

> *"We're less interested in a polished strategy deck and more interested in seeing you
> build something that runs. A rough prototype that works beats a beautiful plan that
> doesn't."*

Three deliverables: a **5–8 minute Loom of it actually running** (named as the most
important artifact), the repo, and a one-page answer to three questions — how you'd
measure impact, how you'd scale it, one tradeoff you made and what production would
do differently.

Two permissions in the brief that this build leans on directly: mocked pieces are
allowed **if the seam is clearly marked**, and AI use is expected rather than
tolerated (*"How you use them is part of what we're evaluating"*).

## Where this sits in the process

Nebius Academy is the education arm of Nebius Group. B2C is TripleTen; **B2B is three
products, and this role is only the third** — the enterprise learning platform, sold
per-client as a solution rather than a course catalogue. B2B selling started April
2025 in the US and LatAm, and **Europe is the new expansion** — the role exists to port
a proven motion to a new region. Reports directly to the CMO, hands-on IC.

TA screen with Ana Herrera passed on **14 Aug 2026**. **This assignment is the next
gate**, and the rounds after it are CMO → the growth marketing team → CRO.

The JD names **"AI Agent Orchestration"** as a responsibility — LLM agents that scrape
competitor ads, rewrite battlecards, summarise media, draft outbound. That is the
strongest single match in the posting, and it is the reason this submission is built
as running software with live adapters rather than as a workflow diagram.

## What is being submitted

**Two tracks, in one app, two tabs.** The brief says to pick one.

> ⚠️ **This is a deliberate over-delivery and it carries a real risk.** The brief
> scores scope judgment explicitly — *"we'd rather see scope judgment than heroics"* —
> so shipping two tracks can read as the exact failure it warns about. The framing that
> answers it, and it needs to be said out loud in the Loom rather than left implied:
> **Track C is the submission. Track A is the second tab**, and both exist because they
> are the same engine pointed at two problems — one config file defining the contract,
> deterministic rules deciding, the model writing only what rules cannot, and every
> unmeasured cell declared rather than defaulted. That is one argument demonstrated
> twice, not two assignments.

**Track C — Agent Engine Optimization.** A fixed buyer-intent query set plus an optional
live ad-hoc query, reported as a benchmark: *"we appear in 3 of 10 queries"*, target
10 of 10. Where competitors appear and we do not, the tool pulls what their cited
sources have that ours don't and turns that into recommendations.

**Track A — inbound lead engine.** Type a real person's name, surname and email; it finds
their actual LinkedIn profile and company, scores them on real firmographics, routes
them, and drafts a first-touch message off inferred pain points. Built so that real
people can be typed in and the output checked against reality.

## What already exists

Three commits of working prototype, carried over whole from `../aeo-monitor` with its
history. It runs end to end on mock data. What that means for the remaining work: the
storage layer, the analysis layer, the dashboard and the seam discipline are **done and
not to be rebuilt** — `aeo/db.py`, `aeo/analyze.py`, `aeo/leads.py`,
`web/static/index.html` and `scripts/seed_synthetic.py` are inherited, not authored here.

What the prototype does **not** have, and what this repo is for: **every external
integration is unverified.** Zero real API calls had been made when this project
started. Enrichment was a five-row fixture dict; the AEO engines had never been run
against a live key.

Three design decisions from that prototype survive intact, because they are the
argument:

1. **Appearing is not binary.** *Cited* (the answer carried a link) and *mentioned*
   (named, no link) need different fixes, so they are different states.
2. **The cited domains are the output.** AI answers ground on third-party sources, so
   the lever is usually not your own site. Ranking what the answers actually cite turns
   a dashboard into a list of places to go and get placed.
3. **No composite 0–100 score.** One number that moves for reasons you cannot recover
   is worse than three you can act on.

And two bugs the sample set caught, both already fixed, both worth keeping in the
walkthrough because they are the kind of thing that makes a scoring system quietly
wrong rather than loudly broken:

- **`intern` matched inside "no INTERNal training capability"** and disqualified a real
  L&D Manager. Substring matching, failing silently toward rejection.
- **Fit alone routed a no-intent lead to sales on a five-minute SLA** — a webinar
  registrant who never attended, earning the slot purely on headcount, seniority and
  industry. Fit and intent are separate gates now.

## The four constraints

These are load-bearing. Each one is a specific failure mode being designed out, not a
preference.

**1. Financials stay unknown, and are never guessed.** Revenue and valuation are not
obtainable for most private companies, and a model asked to find them will invent them
fluently. **Headcount and headcount growth from the LinkedIn company page is the real
growth proxy.** Everything else gets an explicit `unknown` and **zero points** — never a
zero that looks like a measurement, and never an estimate that looks like a fact.

**2. Scoring stays deterministic.** The model does pain-point inference and the draft.
**Rules do the score.** An LLM asked to "score this lead out of 100" returns a confident
number it cannot reproduce twice and nobody can audit.

**3. Per-run cost caps on Apify and Serper calls.** A retry loop against a paid actor is
real money. Caps are enforced in code, per run, and a run that hits its cap says so
rather than silently truncating.

**4. No scraped personal data in the committed repo or the exported HTML.** `data/*.db`
is gitignored and stays that way. This extends to `aeo/report.py` — the standalone HTML
export must never carry Track A scraped fields once real people have been typed in.

## Non-negotiable working order

**Nothing gets built on an unverified adapter.** `scripts/probe.py` makes exactly one
call per integration and prints PASS/FAIL with the actual data shape. Any integration
that fails twice becomes a marked seam within 30 minutes and the build moves on — it
does not get debugged into the deadline.

## Known and settled — do not re-research

- **Historic AEO data does not exist.** No API returns what an assistant said last month.
  Backfill is marked in the data (`runs.is_synthetic = 1`), not just in the caption, so
  no chart can render invented history as measured history by accident.
- **Serper returns no AI Overview field.** Tested.
- **Search only ever proposes.** A search result is a candidate, never an answer. Every
  enriched record must reconcile against something we already hold — for Track A, the
  scraped company against the email domain — or it routes to a human. The cost of
  skipping this is not a blank record, it is a confidently wrong one attached to a real
  name.
