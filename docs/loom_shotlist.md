# Loom shot list — 7 minutes

The brief calls this **the most important artifact**. It is not a tour of the UI; it is
evidence that the thing runs and that the person who built it knows what it does and does
not know. No slides, no one-pager on screen — the app, and one live lookup.

---

## Before you hit record

| | |
|---|---|
| **Server on current code** | `python -m uvicorn web.app:app --port 8011` — **drop `--reload` for the take.** A file save mid-run kills the background collection thread and takes the spend with it |
| **Run picker on `run 3 · measured`** | If you left it on a seeded run, you open on invented data |
| **Lead table shows five leads** | A lookup now *appends* to the run on screen rather than replacing it, so rehearsals accumulate. If the table has your test rows in it, `python -m aeo.leads` starts a clean run of five |
| **Rehearse the exact live lookup** | Same name, same email you will type on camera, ~$0.06. Do not discover on the take that the profile does not reconcile |
| **Pick someone whose email domain matches their employer** | The reconciliation check is domain-based; a personal address will disqualify and a mismatched one routes to human review. Both are *good demos* if you mean them, and a bad surprise if you do not |
| **Apify + Anthropic credit** | Both bill; check the balance |
| **Close the other browser tabs** | Apify console and Claude billing pages have been in every screenshot so far |

---

## 0:00 – 0:40 · What this is, and the scope decision

Say this first, out loud, before anything is on screen. The scope question is the one
they will open the next interview with — answer it before it is asked.

> "The brief said pick one track. I shipped two, and I want to be straight about why
> rather than let you wonder. They are the same engine pointed at two problems: one config
> file holds the contract, deterministic rules make every decision, the model does only
> what rules cannot do, and anything unmeasured is declared instead of quietly scored
> zero. Track A — the inbound lead engine — is the submission. Track C is the second
> half, because it is the same argument against a harder problem. If you think that is the
> over-scoping the brief warns about, that is a fair read and I would rather discuss it
> than hide it."

Then name the three things you deliberately did **not** build. Have them ready:
per-market query sets, live ChatGPT/Perplexity keys, CRM write-back.

## 0:40 – 2:40 · Inbound leads — and one lookup, live

1. **The table.** Five leads, four routes. Point at the columns: `Score / 198`,
   `Intent / 93`. *"105 of that ceiling is firmographic, 93 is behaviour, and the gates
   are separate — a perfect company with no buying signal cannot reach sales."*
2. **Expand Satya Nadella.** The point is the decomposition, not the number:
   *"every point names its source. And this block —"* (Not scored — and not scored as
   zero) *"— is revenue, valuation and funding. They are unobtainable for private
   companies, and a model asked for them invents fluent, specific, unfalsifiable numbers.
   So they are named as unknowns worth zero points, not silently treated as zeroes."*
3. **The draft, and the green chips beneath it.** *"The model declares which record facts
   it leaned on. A draft that cites nothing is a mail-merge in costume, and the dashboard
   counts those."*
4. **Now type a real person live.** Name, surname, work email, tick **Booked a demo**.
   **Do not talk over the stage rail — let it run and read it.** Those lines are the
   enrichment trace being written, streamed out as it happens:

   ```
   profile proposed: https://www.linkedin.com/in/arvindkrishna
   person record from dev_fusion
   company lookup: linkedin.com/company/ibm
   reconciliation: verified — company website matches the email domain
   scoring against config/leads.yaml
   routed hot — inferring pain points and drafting
   ```

   Then narrate the one that matters: *"reconciliation verified — the scraped company's
   website matches the email domain. That check is there because the top search hit for
   a common name is a different real person often enough to matter, and an unreconciled
   record does not score badly, it scores* well*, with every field looking complete."*
5. When it lands: read the reconciliation verdict, the score, the route. **Then untick
   the demo box conceptually:** *"leave every behaviour box unticked and this lead cannot
   go hot however good the company is. That is the intent gate, and it is there because
   the first version sent a webinar no-show to sales on a five-minute SLA."*

## 2:40 – 3:30 · Lead logic

The flowchart, then the rule tables underneath.

> "This is the pipeline with the counts from the last real run on every node — not an
> illustration. A branch that never fired reads zero. The colour on the left edge is what
> *kind* of step it is, and keeping those apart is the whole design: the fallible steps —
> search, scrape, model — are fenced off from the deciding steps, which are rules."

One story here, and it is the best one in the repo:

> "Apify's scraper hit its free-plan cap mid-project. It did not error — it *succeeded*,
> and returned a dataset containing one item: an error message. Every field mapped to
> null, and the lead flowed on and scored as a person with 'no job title found' — which my
> scorer is designed to treat as an honest unknown. My billing status had been laundered
> into a fact about a human being. That is the exact failure this whole submission argues
> against, and I found it inside my own adapter."

## 3:30 – 5:30 · AI visibility — the harder half

1. **Score: 0 of 90.** Do not apologise for it. *"One number, and it comes apart. Answer
   rank is excluded — nothing named us, so there is no position to hold, and those ten
   points are held out of the denominator rather than scored as a failure. That is why it
   reads 0 of 90 and not 0 of 100."*
2. **0 of 10.** *"A count, never a percentage — a percentage hides its denominator, and
   the denominator is where these dashboards lie. And the branded controls are excluded:
   asking 'what is Nebius Academy' and counting the answer is free marks."*
3. **The source gap — this is the slide a CMO acts on.** *"Knowing we lose ten queries is
   not actionable. Knowing the answers that beat us lean on 102 editorial roundups, four
   analyst pieces and two competitor blogs names the places to go and get placed. And the
   classification is a lookup, not a model call — a source type that changed its mind
   between runs would make every recommendation unreproducible."*
4. **SEO → AEO.** *"Everyone in this category asserts an answer. Here it is measured: 30
   of 34 cited domains were also ranking organically for the same query, captured from the
   same response. So here, ranking still buys citations — the lever is placement on pages
   that already rank, not a new content programme."*
5. **Click "See what winning looks like →".** 0 of 90 becomes 55 of 100.
   *"Same board, seeded data — and the banner says so, because the flag lives in the
   database row, not in a caption. This is what the tool looks like once placements land,
   and it is why the zero is a starting line rather than a dead end."* Click back.
6. **Ask one live — this is the live Track C demo.** Scroll to **Ask an ad-hoc query**,
   type a buyer question, and let the rail run (~30 seconds):

   ```
   asking Claude…
   Claude: absent, 7 citation(s)
   asking Google AI Overviews…
   Google AI Overviews: absent, 3 citation(s)
   ChatGPT: unmeasured — declared seam, never called
   Perplexity: unmeasured — declared seam, never called
   ```

   Two things to say over it: *"that is live, right now, against the real engines — and
   the two without keys say 'never called' rather than quietly reporting nothing."* And:
   *"this is deliberately **not** saved. The ten queries are a fixed measurement
   contract, and letting a curious one-off write into the same tables would corrupt
   every comparison to date for the sake of one lookup. It runs, it renders, it's gone."*

7. **The five recommendations**, briefly — written only from the evidence tables, never
   from the raw answers.

## 5:30 – 6:20 · AEO logic — the argument in one screen

> "Two hatched paths, and they are not the same claim. Forty readings were never collected
> because there is no key for ChatGPT and Perplexity — declared seams, never called.
> Twenty were asked for and came back empty, because my Anthropic credit ran out mid-run.
> Both store as unmeasured and both are excluded from every rate, but a run where the
> second number climbs is a broken instrument, and one where only the first is high is
> simply a narrower one. Folding either into 'absent' would report my own missing
> credentials as evidence about the market."

Worth adding, because it is the strongest thing you can say about your own work:

> "That twenty used to read zero. The fix that made errored readings unmeasured only
> applied going forward and never migrated the rows already stored, so this tab was
> claiming a clean run while twenty dead calls sat in the absent column. I found it, and
> the correction is a committed script rather than a quiet UPDATE, because rewriting
> measurement history silently is the same sin in a different costume."

## 6:20 – 7:00 · Cost, the cron, and what is next

- **Cost is measured, not estimated** — `response.usage` per call, stored per observation.
  A lead is $0.06; a full collection about $3.10.
- **The cron is built and deliberately off.** `workflow_dispatch` only, with the arithmetic
  in the file beside the commented `schedule:` line. *"At $3.10 a run, Mon/Wed/Fri is about
  $40 a month on a personal key to detect movement on a brand currently absent from all
  ten queries. Everything that makes runs comparable is built — the contract hash, the
  repeats, the trend. Only the trigger is off, and it is one uncommented line."*
- **Close with what you would do next, not with a summary:** per-market query sets for
  DE/NL/PL, because AI answers are locale-sensitive and Europe is the expansion this role
  exists to serve.

---

## Lines to avoid

- Do not say "as you can see" — show it instead.
- Do not read the on-screen text aloud; the reviewer can read.
- Do not apologise for the zero, the seams, or the mocked behavioural signals. Each is a
  decision with a reason. State the reason once and move on.
- Do not claim it took four hours if it did not. The CMO's opening question is about scope
  and time, and the only wrong answer is a defensive one.
