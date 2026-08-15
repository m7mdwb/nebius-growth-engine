# Nebius Growth Engine

Two working prototypes for the Nebius Academy Growth Marketing Engineer take-home,
in one app with two tabs.

**Track C — Agent Engine Optimization.** Measures how Nebius Academy appears inside AI
assistants against a fixed set of ten buyer-intent queries, reports it as a count
(*"we appear in 3 of 10"*, target 10 of 10), works out what the answers that beat us
cite instead, and turns that into concrete recommendations.

**Track A — inbound lead engine.** Type a real person's name, surname and work email.
It finds their actual LinkedIn profile, reads their company, scores them on real
firmographics, routes them hot / warm / revisit-in-6-months, and drafts a first-touch
message off inferred pain points.

Everything below runs against live APIs. Where something is mocked, it is marked in
the data, not just in a caption.

---

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # ANTHROPIC_API_KEY, APIFY_TOKEN, SERPER_API_KEY

python scripts/probe.py                     # FIRST. one call per integration, PASS/FAIL
uvicorn web.app:app --reload                # http://127.0.0.1:8000
```

Then press **Run live collection** (Track C) or **Run lead engine** (Track A), or type a
real person into the Track A form.

```bash
python -m aeo.run                     # one full collection (12 queries)
python -m aeo.run --limit 3           # a few cents, for when you're changing things
python -m aeo.report                  # -> out/aeo_report.html, one file, no server
python scripts/seed_synthetic.py --weeks 3     # marked backfill, so the trend has a shape
python scripts/seed_synthetic.py --snapshots   # marked prior headcount, so growth computes
```

**No keys?** It still runs. Every engine degrades to a declared seam and the dashboard
draws them as seams — which is the point.

---

## Start with the probe

`scripts/probe.py` makes **exactly one call per integration** and prints PASS/FAIL with
the actual data shape.

It exists because the code in this repo was originally written against documentation
and had never been executed. A mocked prototype and a broken integration look identical
from the outside — both render a dashboard full of plausible cells — and the difference
only surfaces on camera. The probe found four real faults on first contact:

| What it caught | Why it mattered |
|---|---|
| **Claude routed its searches through the code-execution tool**, so answers came back with **zero citations attached** | 6,326 characters of confident answer and nothing to parse. Every cell would have read *mentioned*, never *cited*, and citation share — the actionable metric — would have sat at a flat 0% that reads as a finding rather than a broken instrument |
| `apify-client` 3.x renamed `timeout_secs` → `run_timeout`, and `call()` returns a `Run` object, not a dict | Both engines and both scrapers were dead on arrival and had never been run |
| **harvestapi takes `queries`, not `profileUrls`** | Handed the wrong key it accepted the run, charged for it, and returned **zero items with no error** — indistinguishable from "this person has no profile" |
| `apify~google-search-scraper` rejects any spend cap under $0.50 | A global cost cap cannot serve every actor |

The rule: **nothing gets built on an unverified adapter**, and anything that fails twice
becomes a marked seam within thirty minutes rather than being debugged into the deadline.

---

## Track C — how it works

```
config/queries.yaml   the measurement contract — 10 benchmark queries + 2 controls
        │
        ▼
aeo/engines.py        Claude (web search) · Google AI Overviews (Apify) · 2 seams
        │             every engine returns the same shape
        ▼
aeo/analyze.py        tier the mention · cited domains · competitors · benchmark ·
        │             source gap · SEO/AEO overlap
        ▼
aeo/db.py             SQLite: runs / observations / citations / competitors
        │
        ├── aeo/recommend.py    evidence in, recommendations out
        ├── web/app.py          dashboard, live collection, ad-hoc query, export
        └── .github/workflows/aeo.yml   daily cron → the baseline
```

### Reported as a count, not a percentage

**"We appear in 3 of 10."** A percentage hides its denominator, and the denominator is
where these dashboards go wrong — 30% reads identically whether it is 3 of 10 measured
or 3 of 10 with four cells never looked at. A count forces the denominator onto the
page, and turns the target from "improve visibility" into "we lose these seven specific
questions, and here is who wins them instead".

⚠️ **Branded queries are not in the ten.** Asking *"what is Nebius Academy"* and counting
the answer is free marks. They are asked and reported as controls — if we ever lose our
own name nothing else matters — but they are a sanity check, not the score.

### Four decisions worth arguing about

**1. Appearing is not binary.** *Cited* (the answer carried a link) and *mentioned*
(named, no link) need different fixes, so they are different states. Collapsing them
into "we appeared" throws away the actionable half.

**2. The cited domains are the output.** AI answers ground on third-party sources, so
the lever is usually **not** your own site. On a real run, **67 of 69 citations across
the lost queries came from third-party roundups and 2 from any vendor's own site.**
That converts a dashboard into a list of places to go and get placed — closer to
digital PR than to on-site SEO.

**3. No composite 0–100 visibility score.** Every commercial tool in this category ships
one. One number that moves for reasons you cannot recover is worse than three you can
act on, so presence, citation share and the competitor set are reported separately.

**4. Does SEO feed AEO — measured, not asserted.** The AI Overviews response carries the
organic SERP alongside the generative answer, so the tool compares the domains the AI
*cited* against the domains *ranking* for the same query. Reported with its sample size
attached, because on a handful of queries that number swings hard.

### Two things it refuses to fake

**A seam is not an absence.** An engine with no credential is recorded as `unmeasured`,
excluded from every rate, and drawn hatched. "We did not look" and "we looked and found
nothing" are different findings and must never look alike. On a real run, one Google AI
Overviews repeat returned no overview at all — recorded as unmeasured, not as an absence.

**Invented history is marked in the data, not the caption.** You cannot know what an
assistant said last month; no API returns it. Backfill is flagged `runs.is_synthetic = 1`
in the database, so no chart can render it as measured history by accident.

### The instrument checks itself

Assistant answers are non-deterministic, so **a single snapshot is a sample, not a
measurement**. A subset of queries is asked more than once, disagreement is stored
rather than averaged away, and the dashboard reports how many cells contradicted
themselves. Movement smaller than that spread is not a result.
`runs.query_set_hash` fingerprints the measurement contract, so changing the queries
breaks the trend line instead of pretending the two halves are comparable.

### The ad-hoc query is deliberately not saved

Ask anything live on the Track C tab. It runs against every enabled engine and renders
— and is **not** written into the benchmark tables. The ten queries are a fixed
contract; a trend line only means something if the question set behind it did not move.

---

## Track A — how it works

```
name + surname + work email
        │
        ▼  Serper:  site:linkedin.com/in "Name" "Company"        1 query
        ▼  Apify:   harvestapi/linkedin-profile-scraper          1 call
        ▼  Apify:   harvestapi/linkedin-company                  1 call
        ▼
   RECONCILE against the email domain  ──▶ verified | weak | mismatch | thin
        │
        ▼  disqualify → score (rules) → route → infer pain points + draft (model)
```

About **$0.025 and 20 seconds per lead.**

### Rules decide, the model writes

Scoring is arithmetic over `config/leads.yaml`. Ask an LLM to score a lead out of 100
and you get a confident number it cannot reproduce twice and nobody can audit. The model
does the two things rules genuinely cannot: infer what this company's AI-adoption
problem probably is, and write a sentence that sounds like a person. Every point in the
score shows where it came from.

### 🔑 Search only ever proposes

The top hit for a common name is a **different real person** often enough that accepting
it unchecked would attach a stranger's career to a real lead. And it would score *well*,
not badly — every field would be complete and plausible. So a record is only accepted if
it reconciles against the **email domain**, the one fact no search engine suggested to
us. A mismatch routes to a human and never reaches the scorer.

### Financials are never guessed

Revenue, valuation and funding are not obtainable for most private companies, and a
model asked for them returns a fluent, specific, unfalsifiable number. They are named in
`never_guessed` and recorded as explicit unknowns worth **zero points**.

**Headcount growth is the real proxy** — and LinkedIn publishes today's number with no
history, so it is *measured across two sightings* rather than looked up. Each run writes
a timestamped `company_snapshots` row; growth computes on the second sighting. Until
then it reads "not yet measured" rather than drawing a 0% that looks flat.

### Unknown is not zero

A factor we could not measure is listed in `gaps` — never scored as zero and never
silently dropped. "We looked and this company is not growing" and "we have never looked"
are different claims, and a dashboard that renders both as a missing row teaches the
reader to treat absence as a negative finding.

### Three bugs the live runs caught

**`intern` matched inside "no INTERNal training capability"** and disqualified a real
L&D Manager. Substring matching, failing silently toward rejection. Word-boundary
matched now.

**Fit alone routed a no-intent lead to sales on a five-minute SLA** — a webinar
registrant who never attended, earning the slot purely on headcount, seniority and
industry. Fit and intent are separate gates now. You can watch this work: look a person
up cold and they cannot go hot however good the company is; tick *booked a demo* on the
same person and the score goes 84 → 139 and the route goes warm → hot.

**The seniority list had no C-suite row.** It named only the L&D buying committee —
CHRO, CLO, CTO — so *"Chairman and CEO"* matched nothing and scored zero on seniority.
SAP's CEO came out below a mid-level L&D manager. Invisible against fixture data,
because the fixtures only ever contained the titles the list was written for. It was
the `gaps` list that made it visible: the rule did not fail loudly, it failed by
omitting a row.

---

## Costs and caps

| | |
|---|---|
| One lead | ~$0.025 — 1 Serper query + 2 Apify calls |
| One full Track C run | roughly $0.60–0.90 in Claude + ~$0.20 Apify |
| The probe | under five cents |

**A retry loop against a paid actor is real money**, so caps live in `aeo/cost.py` and
are set in `config/leads.yaml`. Three layers: a per-provider call counter, Apify's own
server-side `max_total_charge_usd`, and a per-call timeout. Hitting a cap **raises and
is reported** — a capped run that silently returns fewer results is indistinguishable
from a thin day.

## No scraped personal data leaves the machine

`data/*.db` is gitignored and stays that way. `out/` too.

`python -m aeo.report` **redacts by default**: names, work emails, profile URLs and the
drafted messages are stripped from the exported HTML, while everything needed to judge
the method survives — the score, every point that made it, the routing and its
reasoning, the reconciliation verdict, the company firmographics. Pass
`--include-personal` to override, consciously.

---

## Layout

| Path | What it is |
|---|---|
| `CONTEXT.md` | the standing brief — assignment, deadline, constraints |
| `scripts/probe.py` | **step 0** — one call per integration, PASS/FAIL + real shapes |
| `config/queries.yaml` | the measurement contract: 10 benchmark queries + 2 controls |
| `config/leads.yaml` | the qualification policy: ICP, disqualifiers, routing, caps |
| `aeo/engines.py` | one adapter per surface, common return shape |
| `aeo/analyze.py` | mention tiers, benchmark, source gap, SEO overlap |
| `aeo/enrich.py` | Track A: Serper → Apify person → Apify company → reconcile |
| `aeo/leads.py` | Track A: disqualify → score → route → draft |
| `aeo/cost.py` | every call that spends money, and the caps on it |
| `aeo/recommend.py` | evidence in, 3–5 recommendations out |
| `aeo/db.py` | SQLite schema, including `company_snapshots` |
| `aeo/report.py` | standalone HTML export, redacted by default |
| `web/app.py` + `web/static/index.html` | dashboard, single file, no build step |
| `scripts/seed_synthetic.py` | marked backfill — AEO history and prior headcount |

Secrets live in `.env` (gitignored) and in GitHub Actions secrets. A secret not listed
under `env:` in the workflow never reaches the run, and fails as a silent zero rather
than an error.
