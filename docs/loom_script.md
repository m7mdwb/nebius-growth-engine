# Loom — the script

Skim-format. **Bold = say this.** Plain = what to do. Aim 7 min; 8 is the ceiling.
Full reasoning behind each beat is in `loom_shotlist.md`.

---

## 0:00 — Open on the scope question

> **"The brief said pick one track. I shipped two, and I'd rather say why than let you wonder."**
> **"They're the same engine pointed at two problems — one config file holds the contract, rules make every decision, the model does only what rules can't, and anything unmeasured is declared instead of quietly scored zero."**
> **"Track C is the submission. Track A is the second tab."**
> **"Three things I deliberately didn't build: per-market query sets, live ChatGPT and Perplexity keys, CRM write-back."**

---

## 0:40 — Inbound leads

Land on the tab. Point at the header row.

> **"Five leads, four routes. Score out of 198 — 105 of that is firmographic, 93 is behaviour."**
> **"The gates are separate. A perfect company with no buying signal cannot reach sales."**

Expand **Satya Nadella**.

> **"Every point names its source. Headcount 25, seniority 25, function 12."**
> **"And this block — revenue, valuation, funding — is *not scored as zero*. They're unobtainable for private companies, and a model asked for them invents fluent, specific, unfalsifiable numbers. So they're named as unknowns."**

Scroll to the draft, point at the green chips.

> **"The model declares which record facts it leaned on. A draft citing nothing is a mail-merge in costume — and the dashboard counts those."**

---

## 1:40 — Type a real person, live

```
Judith · Wiese · judith.wiese@siemens.com
☑ Completed the AI readiness assessment    ☑ Visited pricing
```

> **"A real person, and a work email built from the corporate pattern — the pipeline only uses the domain, because the domain is the one fact no search engine proposed to us."**

**Stop talking. Let the rail run.** Then read it:

> **"Profile proposed. Person record from dev_fusion. Company lookup. Reconciled."**
> **"That's the enrichment trace being written, streamed out as it happens — not a progress bar guessing at twenty seconds."**

When the card lands:

> **"Verified on two things now: the company website matches the email domain, *and* the profile name matches the mailbox."**
> **"That second check exists because the top hit for a name at a 278,000-person company is often a different employee — and that record doesn't score badly, it scores *well*, with every field complete."**
> **"Chief People Officer, Siemens, 278,000 staff. 122 points, hot."**
> **"If I'd left those two boxes unticked she'd score 82 and route warm. A big company with the right title is not a buying signal."**

*(If it fails: `Roland Busch / roland.busch@siemens.com`, also tested.)*

---

## 3:00 — Lead logic

> **"The pipeline with the counts from the last real run on every node — not an illustration. A branch that never fired reads zero."**
> **"The colour on the left edge is what *kind* of step it is. The fallible ones — search, scrape, model — are fenced off from the deciding ones, which are rules."**

The story:

> **"Apify's scraper hit its free cap mid-project. It didn't error — it *succeeded*, and returned a dataset containing one item: an error message."**
> **"Every field mapped to null, and the lead scored as a person with 'no job title found' — which my scorer treats as an honest unknown."**
> **"My billing status had been laundered into a fact about a human being. That's the exact failure this submission argues against, and I found it inside my own adapter."**

---

## 3:50 — AI visibility

> **"One number, and it comes apart. Answer rank is *excluded* — nothing named us, so there's no position to hold, and those ten points are held out of the denominator rather than scored as a failure. That's why it reads 1 of 90, not 1 of 100."**

Point at **0 of 10**.

> **"A count, never a percentage. A percentage hides its denominator, and the denominator is where these dashboards lie."**
> **"Branded queries are excluded — asking 'what is Nebius Academy' and counting the answer is free marks."**

Scroll to the source gap. **This is the CMO's slide.**

> **"Knowing we lose ten queries isn't actionable. Knowing the answers that beat us lean on 43 editorial roundups, three analyst pieces and two competitor blogs — that names the places to go and get placed."**
> **"And the classification is a lookup, not a model call. A source type that changed its mind between runs would make every recommendation unreproducible."**

SEO panel:

> **"Everyone in this category asserts an answer to this. Here it's measured: 30 of 34 cited domains were also ranking organically for the same query, captured from the same response."**
> **"So here, ranking still buys citations. The lever is placement on pages that already rank — not a new content programme."**

Click **See what winning looks like →**.

> **"Same board, seeded data — and the banner says so, because the flag lives in the database row, not in a caption."**
> **"1 of 90 becomes 55 of 100. That's what this looks like once placements land."**

Click back.

---

## 5:20 — Ask one live

Scroll to **Ask an ad-hoc query**. Type a buyer question. Let the rail run.

> **"Live, right now, against the real engines."**
> **"And the two without keys say 'never called' rather than quietly reporting nothing."**
> **"This is deliberately not saved. The ten queries are a fixed measurement contract — letting a curious one-off write into the same tables would corrupt every comparison to date."**

---

## 6:00 — AEO logic

> **"Two hatched paths, and they are not the same claim."**
> **"Forty readings were never collected — no key for ChatGPT and Perplexity, declared seams, never called."**
> **"Twenty were asked for and came back empty, because my Anthropic credit ran out mid-run."**
> **"Both store as unmeasured, both are excluded from every rate. But a run where the second number climbs is a broken instrument. Folding either into 'absent' would report my own missing credentials as evidence about the market."**

If there's room:

> **"That twenty used to read zero. The fix that made errored readings unmeasured only applied going forward and never migrated the rows already stored. I found it — and the correction is a committed script, not a quiet UPDATE, because rewriting measurement history silently is the same sin in a different costume."**

---

## 6:40 — Cost, the cron, close

> **"Cost is measured, not estimated — read off response.usage per call. A lead is six cents, a full collection about three dollars ten."**
> **"The cron is built and deliberately off. At $3.10 a run, Monday-Wednesday-Friday is about forty dollars a month on a personal key, to detect movement on a brand currently absent from all ten queries."**
> **"Everything that makes runs comparable is built — the contract hash, the repeats, the trend. Only the trigger is off, and it's one uncommented line."**

Close forward, not with a summary:

> **"First thing I'd add: per-market query sets. AI answers are locale-sensitive, and Europe is the expansion this role exists to serve."**

---

## Don't

- Don't say "as you can see" — show it.
- Don't read the screen aloud.
- Don't apologise for the zero, the seams, or the mocked behavioural signals.
- Don't claim four hours if it wasn't. The scope question is coming; the only wrong answer is a defensive one.

## Before you record

- Server up **without** `--reload` (a file save mid-run kills a collection).
- Run picker on **run 3 · measured**.
- Table shows the clean five — lookups now *append*, so rehearsals accumulate. `python -m aeo.leads` resets it.
- Rehearse the exact lookup you'll do on camera.
- Close the Apify and Claude billing tabs.
