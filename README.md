# AEO Monitor

Measures how a brand appears inside AI assistants and generative search, and turns
that into something you can act on.

Built for the Nebius Academy take-home, Track C. Runs locally, stores history in
SQLite, and exports a self-contained HTML report that needs no server and no keys.

---

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY (and APIFY_TOKEN if you have one)

python -m aeo.run             # collect once
uvicorn web.app:app --reload  # dashboard at http://127.0.0.1:8000
```

The dashboard's **Run live collection** button does the same thing from the browser
and streams progress, so a walkthrough shows real data arriving rather than a
screenshot of it.

```bash
python scripts/seed_synthetic.py --weeks 3   # marked backfill, so the trend view has a shape
python -m aeo.report                         # -> out/aeo_report.html (one file, no server)
```

**Nothing installed and no keys?** It still runs. Every engine degrades to a declared
seam and the dashboard renders them as seams — which is the point (see below).

---

## What it does

```
config/queries.yaml   the measurement contract — queries, brand aliases, competitors
        │
        ▼
aeo/engines.py        Claude (web search) · Google AI Overviews (Apify) · 2 seams
        │             every engine returns the same shape
        ▼
aeo/analyze.py        tier the mention · extract cited domains · find competitors
        │
        ▼
aeo/db.py             SQLite: runs / observations / citations / competitors
        │
        ├── web/app.py        local dashboard, live collection, export
        └── .github/workflows/aeo.yml   daily cron → the baseline
```

## Three decisions worth arguing about

**1. Appearing is not binary.** *Cited* (the answer carried a link to us) and
*mentioned* (named, no link) need different fixes, so they are different states.
Collapsing them into "we appeared" throws away the actionable half.

**2. The cited domains are the output.** AI answers ground on third-party sources,
so the lever is usually **not** your own site. Ranking the domains the answers
actually cite converts a dashboard into a list of places to go and get placed —
closer to digital PR than to on-site SEO.

**3. No composite 0–100 visibility score.** Every commercial tool in this category
ships one. One number that moves for reasons you cannot recover is worse than three
you can act on, so presence rate, citation share and the competitor set are reported
separately and never blended.

## Two things it refuses to fake

**A seam is not an absence.** An engine with no credential is recorded as
`unmeasured`, excluded from every rate, and drawn as a hatched cell. "We did not
look" and "we looked and found nothing" are different findings and must never look
alike — a rate whose denominator quietly includes unmeasured cells is exactly the
error this tool exists to catch elsewhere.

**Invented history is marked in the data, not the caption.** You cannot know what an
assistant said last month; no API returns it. Backfill is flagged
`runs.is_synthetic = 1` in the database, so no chart can render it as measured
history by accident. It also draws as a shaded column with a warning beneath.

## The instrument checks itself

Assistant answers are non-deterministic. Ask the same question twice and the
competitor set can change, so **a single snapshot is a sample, not a measurement**
— and a monitor built on one sample reports noise as signal.

So a subset of queries is asked more than once (`run.repeats`), disagreement is
stored rather than averaged away, and the dashboard reports how many cells
contradicted themselves. Movement smaller than that spread is not a result.
Production would run five repeats and report a confidence band.

`runs.query_set_hash` fingerprints the measurement contract. Change the queries and
the trend line breaks instead of pretending the two halves are comparable.

---

## Track A — inbound lead engine (second tab)

```bash
python -c "from aeo import leads; leads.collect()"
```
Or the **Run lead engine** button on the Track A tab.

A raw form fill goes in; an enriched, scored, routed lead with a drafted first touch
comes out. Five sample leads, five different outcomes — every branch is exercised.

**Rules decide, the model writes.** Scoring is arithmetic over `config/leads.yaml`.
Ask an LLM to score a lead out of 100 and you get a confident number it cannot
reproduce twice and nobody can audit. The model's job is the one thing rules genuinely
cannot do: write a sentence that sounds like a person. Every point in the score shows
where it came from.

**Disqualifiers run before scoring, and they are absolute.** A strong firmographic
profile must never outvote "personal email, no company". Letting a disqualified lead
win on points is the commonest way one of these quietly poisons a pipeline.

**Unenrichable is not low-scoring.** A lead we could not look up routes to a human, not
to the bottom of the list — the same seam-versus-absence rule the AEO side uses. It
matters more here, because nobody goes looking for the leads that never arrived.

**The draft must cite its evidence.** The model returns which record fields it used. A
draft citing nothing is a mail-merge in costume, and the dashboard counts those.

### Enrichment: mocked here, and this is the production plan

**Waterfall, cheapest source first, stop at the first match.** No single B2B provider
exceeds roughly **70% match rate** on a real inbound list; chaining three to five lifts
it to **85–95%**. That gap is the whole argument — a single provider means one lead in
three arrives blank, and if blanks score as zeroes you are systematically binning a
third of your inbound. It is also why `needs_review` exists: at 85–95%, about one lead
in ten still won't resolve, and that one needs a human, not a low number.

| Step | Gives | Cost | Why it sits there |
|---|---|---|---|
| First-party form | email, company as typed, self-declared role, assessment answers | free | Ours, and more current than anything purchasable |
| Domain heuristics | domain, free-provider detection, MX validity | free | Catches disqualifiers before spending a credit |
| Apollo.io | firmographics, headcount, industry, title | free tier → ~$49/user/mo | Widest cheap coverage, strongest in North America |
| Cognism | EU firmographics, phone-verified contacts, consent/DNC | enterprise | The EU step, and not optional — see below |
| Clay | orchestration across 100+ sources | from ~$185/mo | Replaces a hand-built chain past ~3 providers |

**Cognism is in there for a specific reason.** Nebius Academy is expanding into Europe,
where enrichment and outbound sit under GDPR legitimate interest. Cognism ships DNC
screening and lawful-basis documentation rather than leaving you to argue it afterwards.
US-centric providers have both thinner EU coverage and thinner compliance posture.

**Fields, and how each is verified**, are in `config/leads.yaml` and rendered on the
dashboard. Two rules drive the list: headcount is **banded, never exact**, because
providers disagree by 2–3× and an exact figure makes the score move when the vendor
updates rather than when the company does; and seniority is **derived from the title by
our own rules**, never imported from a vendor's seniority field, because every taxonomy
differs and importing one couples our score to their definitions.

### Two bugs the sample set caught

**`intern` matched inside "no INTERNal training capability"** and disqualified a real
L&D Manager. Substring matching, failing silently toward rejection. Now word-boundary
matched — the same class of bug as `usa` inside `Lausanne`.

**Fit alone routed a no-intent lead to sales on a five-minute SLA.** Someone who
registered for a webinar and never attended, earning the slot purely on headcount,
seniority and industry. Fit and intent are separate gates now; a big company with the
right job title is not a buying signal.

---

## Answering the three questions

**How I'd measure impact.** Baseline first: the same query set, daily, for two weeks,
to establish the noise band — without it there is no way to tell an improvement from
a re-roll. Then three metrics, separately: **presence rate** (any appearance),
**cited rate** (appearances that earn a link), and **citation share** (our sources as
a fraction of all cited sources). The leading indicator is citation share on the
category queries; the lagging one is AI-referred sessions in analytics, which will
stay near zero long after citations start moving.

**How I'd scale it.** What breaks at 10× is the engine calls, not the analysis: this
is one request per query per engine per repeat, run serially. Fan out with a worker
pool and a per-engine rate limiter, move the store from SQLite to Postgres, and cache
answers by content hash so a re-run doesn't re-buy an unchanged answer. Next builds,
in order: the two seam engines made live; an LLM extraction pass for competitor
discovery, which currently only finds rivals cited from their own domains; per-market
query sets (DE/PL/NL), since AI answers are locale-sensitive and this measures one
locale only; and alerting on movement outside the noise band rather than a dashboard
someone has to remember to open.

**One tradeoff, and what production would do differently.** ChatGPT and Perplexity are
**mocked** — no keys on this account. I chose to make the seam explicit rather than
quietly report a smaller matrix, because a missing engine that looks like an absence
would corrupt every rate on the page. Each is one function with the same signature as
the live ones; it is a credential gap, not a design gap. The second tradeoff is the
locale: one query set, one market. Both were scope calls against the four-hour cap,
not discoveries.

---

## Layout

| Path | What it is |
|---|---|
| `config/queries.yaml` | queries, brand aliases, products, competitor seeds, engines, repeats |
| `aeo/engines.py` | one adapter per surface, common return shape |
| `aeo/analyze.py` | mention tiers, cited domains, competitors, aggregation |
| `aeo/db.py` | SQLite schema and access |
| `aeo/run.py` | the collector (`python -m aeo.run`) |
| `aeo/report.py` | standalone HTML export (`python -m aeo.report`) |
| `web/app.py` + `web/static/index.html` | local dashboard, single file, no build step |
| `scripts/seed_synthetic.py` | marked backfill |
| `.github/workflows/aeo.yml` | daily cron |

Secrets live in `.env` (gitignored) and in GitHub Actions secrets. A secret not
listed under `env:` in the workflow never reaches the run, and fails as a silent
zero rather than an error.
