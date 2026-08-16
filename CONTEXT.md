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

**Anthropic credit topped up 15 Aug. Apify on the paid Starter plan 15 Aug.
`scripts/probe.py` = 5/5 PASS.** Both tracks run, every integration verified live.

### ✅ PERSON ENRICHMENT IS LIVE — it took a click *and* $29

The history is worth keeping, because it is two different failures wearing the same
face. `dev_fusion` first refused with `ForbiddenError` (needs account approval). It was
approved — and then refused again for an entirely different reason: *"Users on the free
Apify plan can run the actor through the UI and not via other methods."* Meanwhile
`harvestapi` was past its 20-run free cap. Two actors, two unrelated walls, one symptom.

The Starter plan ($29, and it is spendable credit rather than a fee — dev_fusion bills
$10 per 1,000 profiles, so a lead costs about a cent) cleared both. **`enrich.PERSON_ACTORS`
already tried dev_fusion first, so no code change was needed to switch over — but a code
change was needed the moment it answered**, see below.

⚠️ **And the probe caught the trap on the way in.** dev_fusion returns *none* of
harvestapi's `currentPosition[]` fields. The old mapper read `pos.get("position")` against
a dict that does not exist there, so a perfectly good scrape would have produced
title-from-`headline` and a null company — seniority derived from self-written marketing
copy ("Chairman and CEO at Microsoft") while the structured `jobTitle` ("Chairman and
CEO") sat unread in the same payload. A *thin record*, which the scorer treats as an
honest unknown. `enrich.py` now normalises per actor and stores `source_actor` in the
trace. **Two actors that answer the same question in different shapes is the reason
`probe.py` prints the data shape and not just PASS.**

**Current state: `lead run 11`.** All three enrichable leads carry real structured titles,
exec seniority (+25) and function (+12). Scores 144 / 95 / 124. Four of seven routes fire.

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
> **Track A is the submission. Track C is the second half**, and both exist because they
> are the same engine pointed at two problems — one config file defining the contract,
> deterministic rules deciding, the model writing only what rules cannot, and every
> unmeasured cell declared rather than defaulted. That is one argument demonstrated
> twice, not two assignments.

> 🔄 **This was the other way round until 16 Aug, and the reversal is evidence-based.**
> An external completeness audit scored every lettered requirement in the brief: **Track A
> meets 5 of 5 fully; Track C meets 2 fully and 2 partially** (two of four engines are
> live, and the recurring bonus is built but switched off). Two evaluator-persona reviews
> then landed on the same thing from the other direction: Track A produces a visibly good
> outcome in twenty seconds — type a real person, watch it find, score, route and draft
> them — while **Track C's headline result is a zero**, which is correct and needs a
> paragraph before it reads as competence rather than a broken tool.
>
> Track C is still the stronger *argument* — the source gap is the most original thinking
> here, and the seam-versus-absence distinction is the spine of the whole repo. But a
> reviewer trusts that argument more once Track A has already proved the thing ships. The
> order compounds in one direction and not the other. It also stops the product
> contradicting the claim: the app opens on the lead engine.

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
| **run end-to-end on 3–5 sample leads, show the outputs** | samples + dashboard | 5 samples reaching **four of the seven routes** — hot ×2, warm, disqualified, needs_review. `revisit_6mo`, `hold` and `capped` have never fired and render as `0`, which is a measurement, not a gap |

**The one honest gap, and the brief permits it:** the behavioural signals (assessment
completed, demo booked, webinar attended) are **mocked** — they are first-party events
from systems we have no access to, and the brief says to use realistic mock data and
state the assumption. The firmographics underneath them are real and scraped live. That
split is stated in `config/leads.yaml` and should be said out loud in the Loom.

### Four tabs now — one per track, each with its Logic tab beside it

`Track A — Inbound lead engine` · **`Track A · Logic`** · `Track C — AI visibility` ·
**`Track C · Logic`**

Each Logic tab is a **live flowchart**: stages down a spine with branch-offs to each
terminal state, and **every node carries the count from the last real run**. It is a
picture of what happened, not an illustration of the design — a branch that never fires
reads `0`. The left edge colour-codes what *kind* of step each one is (free / paid call /
rules / model), because keeping those kinds apart is the entire argument.

**Track A · Logic** — nine stages, ending in the four routes.

**Track C · Logic** — eight stages, contract → engines → repeats → classify → benchmark →
source gap → SEO overlap → recommendations. It is built around the one distinction Track C
exists to make, and the layout carries it: **there are two ways a cell ends up without a
reading, and they leave the spine at different points.** A *declared seam* (ChatGPT,
Perplexity — no key) leaves at the engine stage, having never made a call. *Dead air* (an
error, a refusal, an empty answer from a live engine) leaves after the call. Both store
`unmeasured`, neither is ever `absent`, and both are drawn with the same hatch this page
has used for "nobody looked" since the first screen.

⚠️ **On the current run that reads 40 and 20, and the 20 is a scar.** It used to read
`40 and 0`, and this file used to celebrate that zero — wrongly. Commit `925e5b1` fixed
`classify()` so an errored engine stores as `unmeasured`, but it never migrated the rows
already written, so run 3 still held **20 Claude readings that failed with HTTP 400 when
the Anthropic credit ran out mid-collection, filed as `absent`**. The dashboard was
asserting twenty times that we had looked and were not there, on twenty occasions when we
never looked at all — the precise failure this whole project is built to expose, sitting
inside the feature built to expose it.

It survived because every *rate* was already correct: `summarise()` and `benchmark()` both
filter on `error IS NOT NULL`, so the numbers on the page were right while the stored
status underneath them was a lie, waiting for the first consumer that read `status`
directly. The Logic tab was that consumer. Corrected by
`scripts/fix_errored_status.py` — committed rather than run quietly, because a silent
`UPDATE` against measurement history is its own version of the same sin. **The benchmark
and the score did not move (0 of 10, 1 of 90), which is the proof the correction touched
only the stored status and no reported number.**

Both Logic tabs work in the standalone export as well as the live app — verified, they
read the same embedded payload and make no API call.

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
3. **The score is decomposed, not refused.** ⚠️ *This one changed on 16 Aug, and the
   change is deliberate.* The original position was "no composite 0–100 score at all".
   The sharper version: the objection to every commercial tool's score is not that it
   adds up, it is that it adds up **out of sight** — a number that drops cannot tell you
   which of four problems to fix. So `analyze.score()` adds up in public: weights in
   `config/queries.yaml` (hashed separately as `score_hash`, the analogue of Track A's
   `fit_hash`), every component rendered with its own points and the sentence that
   produced it, and **any component that could not be measured is excluded from the
   denominator rather than scored as zero.** The real run reads **1 of 90** — answer
   rank is unmeasurable when nothing named us, so its 10 points are held out and said
   so. A seeded run reads **55 of 100** with all four live.
   This also settles an inconsistency: Track A scored leads out of ~100 with every
   point sourced while Track C refused to score at all, and a reviewer comparing the
   two tabs would have found that harder to defend than either position alone.

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
