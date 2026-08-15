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

## 🚦 Where things stand — read this first

**Anthropic credit topped up 15 Aug. `scripts/probe.py` = 5/5 PASS.** Both tracks run.

### 🔴 ONE ACTION BLOCKS TRACK A, and it is a click

**Apify's `harvestapi` person scraper caps free accounts at 20 runs. We are past it.**
Company enrichment still works (separate per-actor count); *person* enrichment does not,
so no lead can earn seniority or function points.

**Fix: approve `dev_fusion` once, here —**
`https://console.apify.com/actors/2SyF0bVxmgGr8IVCZ?approvePermissions=true`

It wants full account access, which is why it was never enabled; it has no free-run cap.
`enrich.PERSON_ACTORS` already tries it **first**, so approval is the whole fix — no code
change. **Then re-run the lead engine**, because the run currently in the database was
collected while the scraper was blocked and its scores are missing seniority (+25) and
function (+12).

⚠️ **Apify is a $5/month free plan and is the binding constraint on this whole project**
— it funds Track A enrichment *and* the Track C AI Overviews engine. ~$1.63 used.
Rehearse Track C with `--limit 3 --engine claude` (zero Apify).

### 🔑 The bug that block taught us, and it is the best story in the repo

harvestapi does not *fail* on the 21st run. It **succeeds**, and the dataset contains one
item: `{"error": "Free users are limited to 20 runs..."}`. So `items` was non-empty, every
field mapped to `None`, and the lead flowed on to be scored as a person with **"no job
title found"** — which the scorer is designed to treat as an honest unknown.

**Our billing status had been laundered into a fact about the lead.** That is the exact
seam-versus-absence failure this whole project argues against, found inside our own
adapter. `cost.ActorRefused` now catches a refusal-shaped result for every actor, and a
blocked scrape routes to a human with the reason attached instead of scoring as thin.

**Worth telling in the Loom.** It is the thesis of both tracks, caught red-handed in our
own code, and fixed.

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

### Track A against the brief, bullet by bullet — all four covered

| The brief asks for | Where it is | Note |
|---|---|---|
| **enriches it** (company, size, industry, role seniority) — *"real enrichment tool or mocked"* | `aeo/enrich.py`, 5 live providers | **Real, not mocked.** Serper → Apify person → Apify company, reconciled against the email domain |
| **scores or qualifies against a fit definition you design** | `config/leads.yaml` | 6 factors + 4 disqualifier classes, versioned by `fit_hash`. Arithmetic, never a prompt |
| **routes it** (*"MQL to nurture vs. hot lead to Sales"*) | `leads.route()` | hot (5 min) · warm (24h) · revisit_6mo · hold, **plus** disqualified / needs_review / capped |
| **drafts a genuinely personalized first-touch message** | `leads.draft()` | Pain points inferred from the company's own words; `facts_used` declared per draft; generic drafts counted |
| **run end-to-end on 3–5 sample leads, show the outputs** | samples + dashboard | 5 samples, and **every branch fires** |

**The one honest gap, and the brief permits it:** the behavioural signals (assessment
completed, demo booked, webinar attended) are **mocked** — they are first-party events
from systems we have no access to, and the brief says to use realistic mock data and
state the assumption. The firmographics underneath them are real and scraped live. That
split is stated in `config/leads.yaml` and should be said out loud in the Loom.

### Three tabs now

`Track A — Inbound lead engine` · **`Track A · Logic`** · `Track C — AI visibility`

The Logic tab is a **live flowchart**: nine stages down a spine with branch-offs to each
terminal route, and **every node carries the count from the last real run**. It is a
picture of what happened, not an illustration of the design — a branch that never fires
reads `0`. The left edge colour-codes what *kind* of step each one is (free / paid call /
rules / model), because keeping those kinds apart is the entire argument.

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

## What it costs to run

⚠️ **These numbers were wrong until the code started reporting its own spend.** The
first version of this table said a full Track C run cost $0.80–1.10, reconstructed from
call counts and stored answer lengths. It **omitted the web_search tool**, which bills
**$10 per 1,000 searches** — about **$0.80 of a single run on its own**. Search results
are also injected into the *input*, so a one-line query reaches the model as tens of
thousands of tokens: the half of the bill you cannot see from the answer text is the
half that dominates it.

`aeo/pricing.py` now reads `response.usage` off every call and stores it per
observation, so this table is a query (`db.run_cost()`), not an estimate.

| | |
|---|---|
| One Track A lead | **~$0.05** — Anthropic draft, plus 1 Serper query + 2 Apify calls |
| One full Track C run (80 steps) | **~$2.45** Anthropic (incl. ~$0.80 web search) + ~$0.65 Apify |
| Track C, `--limit 3 --engine claude` | **~$0.35**, and zero Apify — the rehearsal setting |
| `scripts/probe.py`, all five | under five cents |
| The written recommendations | ~$0.15, one Opus call |

### Three separate bills, and the smallest one binds

**Anthropic** is metered credit — it hit zero mid-run on 15 Aug and every Claude call in
that run returned a 400.

**Apify is the FREE plan: $5/month.** This is the real constraint. Every AI Overviews
query and every lead lookup spends it, and when it runs out both the Track C engine and
all of Track A enrichment stop. Rehearse with `--engine claude` (no Apify) and save the
budget for the take.

**Serper** — 2,500 free credits, one per lead. Not a constraint at this volume.

## ⏱️ The cron is built and deliberately switched off

`.github/workflows/aeo.yml` is `workflow_dispatch` only — a "Run workflow" button.

At the corrected **~$2.45/run**, a Mon/Wed/Fri schedule is **~$32/month on a personal
key** that has already hit zero once. Paying that continuously to detect movement on a
brand currently absent from 10 of 10 queries is buying a baseline nobody is reading yet.
The `schedule:` block is commented, not deleted, with the arithmetic beside it — turn it
on once the first placements land and a re-run would be expected to move.

**This is a deliberate answer to the brief's bonus** (*"make the monitoring recurring"*),
not a gap: everything that makes runs comparable over time is built and working —
`query_set_hash` breaks the trend line when the contract changes, repeats measure the
noise band, the trend view reads the history. Only the trigger is off, and it is one
uncommented line. Say that out loud in the Loom; scope judgment is scored.

⚠️ **The workflow also used to `git add -f data/aeo.db`** — force-committing the
gitignored database on a schedule. That database now has a `leads` table. CI only runs
Track C so it should always be empty, but "should be" is not a control: the job now
fails loudly if it finds any lead rows before the commit step.

## Two failures worth not re-learning

**SQLite's default busy timeout is zero.** A Track C collection is ~25 minutes that
commits after every observation. Looking up one lead in the web app at the same time —
an entirely reasonable thing to do mid-walkthrough — killed the collector at step 12 of
80 with `database is locked` and threw away the run and the money spent on it. Fixed
with `PRAGMA busy_timeout = 15000` and WAL. **If this reappears, it is not a code bug,
it is that pragma going missing.**

**A truncated model response reports itself as a JSON error.** Both the lead draft and
the recommendations hit `max_tokens` at different points, and the naive handler said
"not valid JSON" — which sends you hunting for a schema bug that does not exist. Both
now check `stop_reason` before parsing and say which failure it actually was.

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
