# Loom — the script

Skim format. **Bold = say this.** Plain = what to do. 7 minutes; 8 is the ceiling.
Reasoning behind each beat is in `loom_shotlist.md`.

Order is **logic → the screen it explains**, per track, then the live demos.

---

## 0:00 – 0:45 · Frame, and kill the scope question

- **"The brief said pick one track. I shipped two, and I'd rather say why than let you wonder."**
- **"Same engine, two problems: one config file holds the contract, rules make every decision, the model does only what rules can't."**
- **"Track A — the inbound lead engine — is the submission. Track C is the second half, because it's the same argument against a harder problem, where the answer comes back zero."**
- **"Three things I deliberately didn't build: per-market query sets, live ChatGPT and Perplexity keys, CRM write-back."**

## 0:45 – 2:00 · Lead logic

- **"Nine stages, and every node carries the count from the last real run — not an illustration. A branch that never fired reads zero."**
- **"The left edge is what *kind* of step it is. The fallible ones — search, scrape, model — are fenced off from the deciding ones, which are rules."**
- Point at stage 5. **"Reconciliation is the step that makes everything after it trustworthy."**
- **The story:** **"Apify's scraper hit its free cap. It didn't error — it *succeeded*, and returned a dataset containing one item: an error message. Every field mapped to null, and the lead scored as a person with 'no job title found', which my scorer treats as an honest unknown."**
- **"My billing status had been laundered into a fact about a human being. That's the exact failure this submission argues against, and I found it inside my own adapter."**
- Scroll to the tables. **"Every weight, read live from the config file — so the explanation can't drift from the rules it's explaining."**

## 2:00 – 4:00 · Inbound leads, and the live lookup

- **"Five leads, four routes. Score out of 198 — 105 firmographic, 93 behavioural, and the gates are separate. A perfect company with no buying signal cannot reach sales."**
- Expand **Satya Nadella**. **"Every point names its source."**
- **"And revenue, valuation and funding are *not scored as zero*. They're unobtainable for private companies, and a model asked for them invents fluent, specific, unfalsifiable numbers."**
- Point at the green chips. **"The model declares which facts it leaned on. A draft citing nothing is a mail-merge in costume, and the dashboard counts those."**

**Type live:** `Judith · Wiese · judith.wiese@siemens.com` — tick ☑ assessment ☑ pricing

- **"A real person, and a work email from the corporate pattern — the pipeline only uses the domain, because the domain is the one fact no search engine proposed to us."**
- **Stop talking. Let the rail run.** Then: **"That's the enrichment trace being written, streamed as it happens — not a progress bar guessing at twenty seconds."**
- **"Verified on two things: the company website matches the email domain, *and* the profile name matches the mailbox."**
- **"That second check exists because the top hit for a name at a 278,000-person company is often a different employee — and that record doesn't score badly, it scores *well*, with every field complete."**
- **"Chief People Officer, Siemens, 278,000 staff. 122 points, hot. Untick those two boxes and she scores 82 and routes warm."**

*(Backup: `Roland Busch / roland.busch@siemens.com`, tested.)*

## 4:00 – 5:00 · AEO logic

- **"Two hatched paths, and they are not the same claim."**
- **"Forty readings were never collected — no keys for ChatGPT and Perplexity, declared seams, never called."**
- **"Twenty were asked for and came back empty, because my Anthropic credit ran out mid-run."**
- **"Both store as unmeasured and both are excluded from every rate. But a run where the second number climbs is a broken instrument. Folding either into 'absent' would report my own missing credentials as evidence about the market."**
- **If room:** **"That twenty used to read zero. The fix only applied going forward and never migrated the stored rows. I found it — and the correction is a committed script, not a quiet UPDATE, because rewriting measurement history silently is the same sin in a different costume."**

## 5:00 – 6:30 · AI visibility, and one live query

- **"One number, and it comes apart. Answer rank is *excluded* — nothing named us, so there's no position to hold. That's why it reads 1 of 90, not 1 of 100."**
- **"0 of 10. A count, never a percentage — a percentage hides its denominator, and the denominator is where these dashboards lie."**
- **Source gap — the slide a CMO acts on:** **"Knowing we lose ten queries isn't actionable. Knowing the answers that beat us lean on 43 editorial roundups, three analyst pieces and two competitor blogs names the places to go and get placed."**
- **"30 of 34 cited domains were also ranking organically for the same query — so here, ranking still buys citations. The lever is placement on pages that already rank."**
- **Recommendations:** **"The model writes these, and a lookup — not a second model call — verifies every source it cites against the domains this run actually collected. Twenty references checked, none unsupported."**
- Click **See what winning looks like →**. **"1 of 90 becomes 55 of 100. Seeded, and the banner says so, because the flag lives in the database row rather than a caption."**
- **Ask an ad-hoc query, live.** **"Live, against the real engines — and the two without keys say 'never called' rather than quietly reporting nothing."**
- **"Deliberately not saved. The ten queries are a fixed measurement contract; letting a curious one-off write into those tables would corrupt every comparison to date."**

## 6:30 – 7:00 · Cost, tooling, the cron, close

- **"Cost is measured, not estimated — read off `response.usage` per call. Six cents a lead, $3.10 a full collection."**
- **On the tooling — say this, it's a judgement question:** **"Everything scraped here goes through Apify because I already had an account and could be live the same afternoon. It's a marketplace of third-party scrapers, not a data vendor — and this build showed the cost: two actors doing the same job returned incompatible shapes. In production I'd buy the data, not the scraper. Cognism for European firmographics under GDPR, Clay to orchestrate. And for AI visibility I'd either use a SERP provider with native AI Overview support, or just buy Otterly at twenty-nine dollars a month — what's worth keeping from this build is the source gap and the recommendation layer, which none of them do."**
- **"The cron is built and deliberately off. Mon/Wed/Fri is about forty dollars a month to detect movement on a brand absent from all ten queries. Everything that makes runs comparable is built. Only the trigger is off, and it's one uncommented line."**
- **Close forward:** **"First thing I'd add: per-market query sets. AI answers are locale-sensitive, and Europe is the expansion this role exists to serve."**

---

## Don't

- Don't say "as you can see" — show it.
- Don't read the screen aloud.
- Don't apologise for the zero, the seams, or the mocked behavioural signals.
- Don't claim four hours if it wasn't. The scope question is coming; the only wrong answer is a defensive one.

## Before you record

- Server up **without** `--reload` — a file save mid-run kills a collection.
- Run picker on **run 3 · measured**.
- Table shows the clean five. Lookups *append* now, so rehearsals accumulate; `python -m aeo.leads` resets it.
- Rehearse the exact lookup you'll do on camera.
- Close the Apify and Claude billing tabs.
