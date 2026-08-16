# Loom — the spoken script

Read this the way you'd talk, not the way it's written. `[brackets]` are stage
directions, everything else is out loud. Roughly 1,000 spoken words plus two pauses
where the app is working — about seven minutes.

The reasoning behind each beat is in `loom_shotlist.md` if you want to argue with a
choice before you record it.

---

## 0:00 — Open

*[App open on **Inbound leads**. Don't touch anything yet.]*

Hi — I'm Mohamed. This is the take-home for the Growth Marketing Engineer role, and
I want to open with the question you're going to ask me anyway.

The brief said pick one track. I built two. So let me give you the reasoning, and
then you can tell me whether you think that was the wrong call.

They're the same engine pointed at two different problems. One config file holds the
contract. Rules make every decision. The model only does the two things rules
genuinely can't do. And anything we didn't measure gets declared, rather than quietly
scored as a zero.

Track A — the inbound lead engine — is my submission. Track C is the second half,
because it's the same argument against a harder problem, where the answer comes back
zero.

And three things I deliberately didn't build: per-market query sets, live keys for
ChatGPT and Perplexity, and CRM write-back.

---

## 0:45 — Lead logic

*[Click **Lead logic**.]*

I'll show you how it decides first, then show you it running.

Nine stages. Every node carries the count from the last real run, so this is a picture
of what actually happened — not a diagram of what I intended. If a branch never fired,
it reads zero and says so.

The colour on the left edge is what *kind* of step it is. Grey is free, orange costs
money, blue is rules, purple is the model. Keeping those apart is the whole design.
The fallible steps — search, scraping, the model — are fenced off from the steps that
actually decide anything.

*[Point at stage 5.]*

Stage five is the one that matters. Reconciliation. Everything after it is only
trustworthy because of it, and I'll come back to that in a minute.

Here's the story I'd most want you to hear.

Apify's scraper hit its free-plan cap halfway through this project. It didn't error.
It *succeeded* — and returned a dataset containing exactly one item, which was an
error message. So every field mapped to null, and the lead flowed on and got scored as
a person with "no job title found". Which my scorer is designed to treat as an honest
unknown.

My billing status had been laundered into a fact about a human being.

That's precisely the failure this whole submission argues against, and I found it
inside my own code. It's caught now — a refused scrape goes to a person, with the
reason attached.

*[Scroll down to the tables.]*

And underneath the flow is every weight, read live from the config file. So the
explanation can't drift away from the rules it's explaining, which is the usual way a
scoring model ends up documented as something it no longer is.

---

## 2:00 — Inbound leads

*[Click **Inbound leads**.]*

Five sample leads, four different routes.

The score is out of 198. A hundred and five of that is firmographic — company size,
growth, seniority, function, industry — and ninety-three is behaviour. The two gates
are separate, which means a perfect company with no buying signal still can't reach
sales.

*[Expand Satya Nadella.]*

Every point names where it came from. And this block here — revenue, valuation,
funding — is *not* scored as zero. Those aren't obtainable for most private companies,
and a model asked for them will invent a fluent, specific, completely unfalsifiable
number. So they're recorded as unknowns instead.

*[Point at the green chips under the draft.]*

The model has to declare which facts from the record it leaned on. A draft that cites
nothing is a mail-merge in costume — and the dashboard counts those, so "personalised"
stays something you can check rather than something you take on trust.

### The live lookup

*[Scroll up to the form. Type: Judith · Wiese · judith.wiese@siemens.com. Tick
"Completed the AI readiness assessment" and "Visited pricing". Click.]*

So let me put a real person through it.

That's a real work email built from the company's pattern. The pipeline only uses the
domain, because the domain is the one fact no search engine proposed to us.

*[STOP TALKING. Let the stage rail run — about twenty seconds. Then read it.]*

That's the enrichment trace being written as it happens. Serper proposed a profile.
The person record came back from one of two Apify actors. Then the company. Then
reconciliation.

And reconciliation checks two things now. The company's website matches the email
domain — and the profile name matches the mailbox.

That second check exists because the top search hit for a name at a company of nearly
three hundred thousand people is very often a *different employee*. And a record like
that doesn't score badly. It scores *well*, because every field looks complete.

Chief People and Sustainability Officer at Siemens. Two hundred and seventy-eight
thousand staff. A hundred and twenty-two points, routed hot.

If I untick those two behaviour boxes, she scores eighty-two and routes warm instead.
A big company with the right job title is not a buying signal.

---

## 4:00 — AEO logic

*[Click **AEO logic**.]*

Now the second half — measuring how we show up inside AI assistants.

Same idea: the flow, with the real counts on it. And the thing I care about most is
these two hatched paths, because they are not the same claim.

Forty readings were never collected at all. No keys for ChatGPT and Perplexity, so
those are declared seams — we never called them.

Twenty were asked for and came back empty, because my Anthropic credit ran out
mid-run.

Both of those store as "unmeasured" and both are excluded from every rate. But they
mean different things. A run where the second number climbs is a broken instrument. A
run where only the first is high is just a narrower one. And folding either of them
into "absent" would be reporting my own missing credentials as evidence about the
market.

That twenty used to read zero, by the way. The fix that made errored readings
unmeasured only applied going forward — it never migrated the rows already stored. So
this tab was claiming a clean run while twenty dead calls sat in the absent column. I
found it, and the correction is a committed script rather than a quiet database
update, because silently rewriting measurement history is the same sin in a different
costume.

---

## 5:00 — AI visibility

*[Click **AI visibility**.]*

One number at the top, and it comes apart.

It reads one out of ninety, not one out of a hundred. Answer rank is *excluded* —
nothing named us anywhere, so there's no position to hold, and those ten points are
held out of the denominator instead of counted as a failure.

*[Scroll to the benchmark.]*

Zero of ten. A count, never a percentage. A percentage hides its denominator, and the
denominator is where these dashboards lie — thirty percent reads identically whether
it's three of ten measured, or three of ten with four cells nobody looked at.

*[Scroll to the source gap.]*

This is the part I'd actually act on. Knowing we lose ten queries isn't useful.
Knowing that the answers beating us lean on forty-three editorial roundups, three
analyst pieces and two competitor blogs — that names the specific places to go and get
placed. And that classification is a lookup, not a model call, because a source type
that changed its mind between runs would make every recommendation unreproducible.

*[Scroll to the SEO panel.]*

Everyone in this category asserts an answer to this one. Here it's measured. Thirty of
the thirty-four cited domains were also ranking organically for the same query,
captured from the same response. So for us, right now, ranking still buys citations —
the lever is placement on pages that already rank, not a new content programme.

*[Scroll to the recommendations.]*

The model writes these. And then a lookup — not a second model call — checks every
source it cited against the domains this run actually collected. Twenty references
checked, none unsupported. Rules verify what the model writes, on both tracks.

*[Click "See what winning looks like →".]*

Same board, seeded data. One of ninety becomes fifty-five of a hundred. The banner
says it's seeded because that flag lives in the database row, not in a caption — so no
chart here can render invented history as if it were measured.

*[Click back.]*

### One live query

*[Scroll to "Ask an ad-hoc query". Type a buyer question. Click Ask, then wait.]*

And I can ask one live.

*[Let the rail run, ~30 seconds.]*

That's against the real engines, right now. And notice the two without keys say "never
called" rather than quietly reporting nothing.

This one is deliberately not saved. The ten queries are a fixed measurement contract,
and letting a curious one-off write into those same tables would corrupt every
comparison to date for the sake of one lookup.

---

## 6:30 — Cost, tooling, and what I'd do next

Cost is measured, not estimated — read off the usage field on every call and stored per
observation. About six cents a lead, about three dollars ten for a full collection.

One thing on tooling, because it's a judgement call rather than a technical one.
Everything scraped here goes through Apify, and that's because I already had an account
and could be live the same afternoon. It's a marketplace of third-party scrapers, not
a data vendor — and this build showed the cost of that. Two actors doing the same job
returned completely different response shapes.

In production I'd buy the data, not the scraper. Cognism for European firmographics,
because enrichment and outbound in Europe sit under GDPR legitimate interest and it
ships the lawful-basis documentation. Clay to orchestrate once there's more than about
three providers. And for AI visibility I'd either use a search provider with native AI
Overview support, or honestly just buy Otterly at twenty-nine dollars a month. If
Nebius only wants monitoring, buy the monitoring. What's worth keeping from this build
is the source gap and the recommendation layer — that's the part none of them do.

Last thing. The recurring monitoring is built and deliberately switched off. At three
dollars ten a run, Monday-Wednesday-Friday is about forty dollars a month on a personal
key, to detect movement on a brand that's currently absent from all ten queries.
Everything that makes runs comparable over time is built and working. Only the trigger
is off, and it's one uncommented line.

If I carried this forward, the first thing I'd add is per-market query sets. AI answers
are locale-sensitive, and Europe is the expansion this role exists to serve.

Thanks for watching.

---

## Notes to yourself

- Two silences are deliberate — the lead lookup and the ad-hoc query. Don't fill them.
- Don't say "as you can see". Don't read the screen out loud.
- Don't apologise for the zero, the seams, or the mocked behaviour signals.
- If they ask how long it took, say the real number. The scope question is coming and
  the only wrong answer is a defensive one.

## Before you record

- Server up **without** `--reload` — a file save mid-run kills a collection.
- Run picker on **run 3 · measured**.
- Table showing the clean five. Lookups append now, so rehearsals pile up;
  `python -m aeo.leads` resets it.
- Rehearse the exact lookup you'll do on camera.
- Close the Apify and Claude billing tabs.
