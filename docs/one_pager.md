# Nebius Growth Engine — the three questions

**Track C (AEO) is the submission. Track A (inbound leads) is the second tab.**

Both are here because they are the same engine pointed at two problems: one config file
holding the contract, deterministic rules deciding, the model doing only what rules
cannot, and every unmeasured cell declared rather than defaulted to zero. That is one
argument demonstrated twice, not two assignments.

---

## 1. How I'd measure impact

### Track C

**Headline metric: how many of ten buyer-intent queries we appear in.** A count, not a
percentage — a percentage hides its denominator, and the denominator is where these
dashboards go wrong. "30%" reads identically whether it is 3 of 10 measured or 3 of 10
with four cells nobody looked at. Target is 10 of 10.

**Baseline before anything else.** The same ten queries, daily, for two weeks, to
establish the noise band. Assistant answers are non-deterministic: ask the same question
twice and the competitor set moves. Without that band there is no way to tell an
improvement from a re-roll, and **movement smaller than the spread is not a result.** The
tool already asks a subset of queries three times per run and reports how many cells
contradicted themselves, so the noise band is measured rather than assumed.

**Three metrics, never blended into one score.** No composite 0–100 — every commercial
tool in this category ships one, and a number that moves for reasons you cannot recover
is worse than three you can act on.

| | |
|---|---|
| **Presence** — appear at all | the headline N-of-10 |
| **Citation share** — our sources as a fraction of all cited sources | the leading indicator |
| **Competitor set** — who owns the answer instead | the target list |

Leading indicator is **citation share on the category queries**. Lagging indicator is
AI-referred sessions in analytics, which will stay near zero long after citations start
moving — so judging the programme on it for the first quarter would kill it unfairly.

### Track A

**Speed-to-lead against the SLA** is the operational metric: what share of `hot` leads
were contacted inside five minutes. It is the biggest single lever on inbound conversion
and the one the current manual process is losing.

**Three quality metrics that keep the system honest**, all already on the dashboard:

- **Drafts citing zero facts.** The model declares which record fields each message
  leaned on. A draft citing nothing is a mail-merge in costume, and counting them is the
  only way "personalised" stays a claim you can check rather than one you take on trust.
- **`needs_review` rate.** Leads that could not be looked up or did not reconcile. If it
  climbs, enrichment coverage is degrading — and this is the number nobody watches,
  because nobody goes looking for the leads that never arrived.
- **Reconciliation mismatches.** Records where the scraped profile did not match the
  email domain. Each one is a lead that would otherwise have been scored as somebody else.

**The honest counterfactual** is a holdout: route a random 10% by the old manual process
and compare meeting-booked rate. Without it, any lift gets attributed to the scoring
model when it may just be that someone finally replied within the hour.

---

## 2. How I'd scale it

**What breaks at 10× is the calls, not the analysis.** Both tracks are serial HTTP:
one request per query per engine per repeat, and three per lead. Neither the SQLite
store nor the scoring arithmetic is near a limit.

**Track C at 10×** (100 queries, 4 engines, 5 repeats a day):
- Fan out with a worker pool and a per-engine rate limiter.
- **Cache answers by content hash** so a re-run does not re-buy an unchanged answer.
- Move the store to Postgres — the schema is unchanged, only the driver.
- Then, in order: **make the two seam engines live** (ChatGPT and Perplexity are a
  credential gap, not a design gap — each is one function with the same signature); an
  **LLM extraction pass for competitor discovery**, which currently only finds rivals
  cited from their own domains; **per-market query sets (DE/PL/NL)**, since AI answers
  are locale-sensitive and this measures one locale — and Europe is the expansion; and
  **alerting on movement outside the noise band**, rather than a dashboard someone has
  to remember to open.

**Track A at 10×** (500 inbound leads/week):
- At the measured **$0.06** a lead that is ~$30/week, so **cost is still not the
  constraint — accuracy is.**
- The waterfall needs a second and third provider. No single B2B source exceeds roughly
  **70% match rate** on a real inbound list; chaining three to five lifts it to **85–95%**.
  That gap is the whole argument: one provider means one lead in three arrives blank, and
  if blanks score as zeroes you are systematically binning a third of your inbound.
- **Cognism next specifically**, because Nebius Academy is expanding into Europe and
  enrichment plus outbound there sit under GDPR legitimate interest. It ships DNC
  screening and lawful-basis documentation rather than leaving you to argue it
  afterwards. This stopped being a slide the moment the prototype started scraping real
  people.
- **Queue the enrichment.** Right now a form submission blocks on three HTTP calls. At
  volume that becomes a job with a retry policy — and the retry policy is exactly where
  a paid actor turns into a runaway bill, which is why the caps are already in the code.
- **Write back to the CRM**, which is the real integration. The scoring is worthless if
  a salesperson has to open a separate dashboard to see it.

---

## 3. One tradeoff, and what production would do differently

**The tradeoff: two of four surfaces are unmeasured.** ChatGPT and Perplexity have no
key on this account, so the N-of-10 count reflects Claude and Google AI Overviews only.

I chose to make that a **declared seam** rather than quietly report a smaller matrix.
An engine with no credential is recorded as `unmeasured`, excluded from every rate, and
drawn hatched — because "we did not look" and "we looked and found nothing" are
different findings, and a rate whose denominator silently includes unmeasured cells is
exactly the error this tool exists to catch in other people's dashboards. Reporting
absence for a cell nobody read would have put a fabricated negative into the table.

**Production would close it with two API keys** — each adapter is one function with the
same return shape as the live ones. It is a credential gap, not a design gap.

### Three smaller ones, stated plainly

- **One locale.** English, one query set. AI answers are locale-sensitive and Europe is
  the expansion, so per-market query sets are the first thing I would add after the keys.
- **Headcount growth needs a second sighting.** LinkedIn publishes today's number and no
  history, so growth is measured across two runs rather than looked up. On first contact
  with a company it reads *"not yet measured"* and scores zero. That is the honest
  answer, but it means the growth signal is worth nothing on day one and everything by
  month three. The seeded baseline in the demo is marked `synthetic-backfill` **in the
  database row**, so no chart can present it as measured.
- **Competitor discovery is shallow.** It finds rivals cited from their own domains and
  names it already knows. A rival discussed but never linked is invisible.

### What I would not change

The parts that look like scope cuts are deliberate:

- **No composite visibility score.** Not a missing feature.
- **Financials never estimated.** Revenue and valuation are unobtainable for most
  private companies and a model asked for them invents fluent, specific, unfalsifiable
  numbers. They are named as unknowns worth zero points.
- **Rules score, the model writes.** An LLM asked to score a lead out of 100 returns a
  number it cannot reproduce twice and no salesperson can argue with.

---

## What the build actually found

Worth saying because it is the argument for building rather than diagramming. **Zero
real API calls had been made against this codebase before this project started** — every
adapter was written from documentation and had never been executed. The probe and the
first live runs found, in order:

1. **Claude returned confident answers with zero parseable citations**, because it routed
   its searches through the code-execution tool. Citation share — the actionable metric —
   would have read a flat 0% that looks like a finding rather than a broken instrument.
2. **Two Apify adapters were dead on arrival** on a renamed client argument and a return
   type that changed from dict to object.
3. **The wrong input key made a paid scraper return zero items with no error**, which is
   indistinguishable from "this person has no LinkedIn profile".
4. **The seniority rules had no C-suite row**, so a CEO scored zero on seniority and SAP's
   came out below a mid-level L&D manager. Invisible against fixture data, because the
   fixtures only contained the titles the rules were written for.
5. **Answers were truncating at the token ceiling**, which silently biases an instrument
   whose entire job is counting who gets named.

None of those are visible in a workflow diagram, and four of the five fail *silently* —
they produce plausible output rather than an error. That is the case for the probe, and
for shipping something that runs.
