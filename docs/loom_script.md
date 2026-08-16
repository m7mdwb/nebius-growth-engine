# Loom — the spoken script

Read it the way you'd talk. `[brackets]` are stage directions, everything else is out
loud.

**Timing, measured not guessed: ~1,130 spoken words.** At a normal demo pace (165 wpm)
that is 6:50 plus the two silences — **7:45 total, inside the 8-minute ceiling.** At a
slow, careful pace it runs to 8:40, which is over.

So: **speak at pace, and if you feel slow, drop the three *italic* paragraphs.** They
are the nice-to-haves and they buy back about a minute between them. The rest is load
bearing.

Reasoning behind each beat is in `loom_shotlist.md`.

---

## 0:00 — Open

*[App open on **Inbound leads**. Don't touch anything.]*

Hi, I'm Mohamed. Before I show you anything, let me answer the question you're going to
ask me anyway.

The brief said pick one track. I built two. They're the same engine pointed at two
problems: one config file holds the contract, rules make every decision, the model only
does the two things rules genuinely can't, and anything we didn't measure gets declared
rather than quietly scored zero.

Track A, the inbound lead engine, is my submission. Track C is the second half, because
it's the same argument against a harder problem — one where the answer comes back zero.

Three things I deliberately didn't build: per-market query sets, live keys for ChatGPT
and Perplexity, and CRM write-back.

---

## 0:40 — Lead logic

*[Click **Lead logic**.]*

How it decides, then I'll run it.

Nine stages, and every node carries the count from the last real run — a picture of what
happened, not a diagram of what I intended. If a branch never fired it reads zero.

The colour on the left edge is what *kind* of step it is. The fallible ones — search,
scraping, the model — are fenced off from the ones that decide, which are all rules.

Here's the story I'd most want you to hear.

Apify's scraper hit its free-plan cap halfway through this project. It didn't error. It
*succeeded* — and returned a dataset containing one item, which was an error message.
Every field mapped to null, so the lead scored as a person with "no job title found",
which my scorer treats as an honest unknown.

My billing status had been laundered into a fact about a human being.

That's exactly what this submission argues against, and I found it in my own code. A
refused scrape now goes to a person with the reason attached.

*[Scroll to the tables.]*

*And every weight sits underneath, read live from the config file — so the explanation
can't drift from the rules it's explaining.*

---

## 1:50 — Inbound leads

*[Click **Inbound leads**.]*

Five leads, four routes. Score out of 198 — 105 firmographic, 93 behavioural, and the
gates are separate, so a perfect company with no buying signal still can't reach sales.

*[Expand Satya Nadella.]*

Every point names where it came from. And revenue, valuation and funding are *not*
scored as zero — they aren't obtainable for private companies, and a model asked for
them invents a fluent, specific, unfalsifiable number. So they're recorded as unknowns.

*[Point at the green chips.]*

The model declares which facts it leaned on. A draft citing nothing is a mail-merge in
costume, and the dashboard counts those.

### The live lookup

*[Type: Judith · Wiese · judith.wiese@siemens.com. Tick assessment + pricing. Click.]*

Let me put a real person through it. That's a work email built from the company's
pattern — the pipeline only uses the domain, because the domain is the one fact no
search engine proposed to us.

*[STOP TALKING. ~20 seconds. Then read the rail.]*

That's the enrichment trace being written as it happens. And reconciliation checks two
things: the company website matches the email domain, and the profile name matches the
mailbox.

That second check is there because the top hit for a name at a company of nearly three
hundred thousand people is very often a different employee. And that record doesn't
score badly — it scores *well*, because every field looks complete.

Chief People Officer at Siemens, 278,000 staff, 122 points, hot. Untick those two
behaviour boxes and she scores 82 and routes warm. A big company with the right title
isn't a buying signal.

---

## 3:40 — AEO logic

*[Click **AEO logic**.]*

Second half — how we show up inside AI assistants.

Two hatched paths here, and they are not the same claim. Forty readings were never
collected: no keys for ChatGPT and Perplexity, so those are declared seams. Twenty were
asked for and came back empty, because my Anthropic credit ran out mid-run.

Both store as unmeasured, both are excluded from every rate. But a run where the second
number climbs is a broken instrument, and one where only the first is high is just a
narrower one. Folding either into "absent" would report my own missing credentials as
evidence about the market.

*That twenty used to read zero, incidentally. The fix only applied going forward and
never migrated the stored rows, so this tab claimed a clean run while twenty dead calls
sat in the absent column. I found it — and the correction is a committed script, not a
quiet database update.*

---

## 4:40 — AI visibility

*[Click **AI visibility**.]*

One number, and it comes apart. It reads one of ninety, not one of a hundred — answer
rank is excluded, because nothing named us, so there's no position to hold. Those ten
points are held out of the denominator rather than counted as failure.

*[Benchmark.]*

Zero of ten. A count, never a percentage — a percentage hides its denominator, and
that's where these dashboards lie.

*[Source gap.]*

This is the part I'd act on. Knowing we lose ten queries isn't useful. Knowing the
answers beating us lean on forty-three editorial roundups, three analyst pieces and two
competitor blogs — that names where to go and get placed.

*[SEO panel.]* Thirty of the thirty-four cited domains were also ranking organically for
the same query, so for us, ranking still buys citations.

*[Recommendations.]* The model writes these, and a lookup — not a second model call —
checks every source it cited against what this run actually collected.

*[Click "See what winning looks like →".]*

Same board, seeded data. One of ninety becomes fifty-five of a hundred — and the banner
says it's seeded, because that flag lives in the database row, not a caption.

*[Click back. Scroll to the ad-hoc box, type a buyer question, click Ask.]*

And I can ask one live.

*[STOP TALKING. ~30 seconds.]*

Real engines, right now. The two without keys say "never called" rather than quietly
reporting nothing. And this one isn't saved — the ten queries are a fixed contract, and
letting a one-off write into those tables would corrupt every comparison to date.

---

## 6:20 — Cost, tooling, close

Cost is measured, not estimated — read off the usage on every call. Six cents a lead,
about three dollars ten a full collection.

One judgement call worth naming: everything scraped here goes through Apify because I
already had an account and could be live the same afternoon. It's a marketplace of
third-party scrapers, not a data vendor — two actors doing the same job returned
completely different response shapes. In production I'd buy the data, not the scraper:
Cognism for European firmographics under GDPR. And for AI visibility I'd probably just
buy Otterly at twenty-nine a month. What's worth keeping from this build is the source
gap and the recommendation layer — the part none of them do.

The recurring monitoring is built and deliberately off. Forty dollars a month to detect
movement on a brand absent from all ten queries. Everything that makes runs comparable
is built — only the trigger is off, and it's one uncommented line.

First thing I'd add next is per-market query sets. AI answers are locale-sensitive, and
Europe is the expansion this role exists to serve.

Thanks for watching.

---

## Notes to yourself

- The two silences are deliberate. Don't fill them — the stage rails are more
  persuasive than narration over them.
- Don't say "as you can see". Don't read the screen aloud.
- Don't apologise for the zero, the seams, or the mocked behaviour signals.
- If they ask how long it took, give the real number.

## Before you record

- Server up **without** `--reload` — a file save mid-run kills a collection.
- Run picker on **run 3 · measured**.
- Clean five in the table — lookups append now, so rehearsals pile up.
  `python -m aeo.leads` resets it.
- Rehearse the exact lookup you'll do on camera.
- Close the Apify and Claude billing tabs.
