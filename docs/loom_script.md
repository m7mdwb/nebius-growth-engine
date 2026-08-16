# Loom — what to say

`[brackets]` are what you do. Everything else you say.

Read it out loud once before recording. If a line feels awkward in your mouth, change it
— it should sound like you, not like you're hitting marks.

**1,208 spoken words — counted, not estimated.** That's **8:10** at a normal demo pace,
or 9:00 if you speak slowly. The brief's ceiling is 8 minutes, so speak at pace.

If you want headroom, these four lines are the ones to drop. They're worth about 50
seconds between them and nothing depends on them:

- "Blue is rules, purple is the model…" — the screen already shows it
- "And the model declares which facts it used…"
- "The model writes these, then a plain lookup checks…"
- The whole scheduled-version paragraph near the end

Everything else earns its place. The Apify story is the longest single block and it is
the one to protect.

---

## Open

*[On **Inbound leads**. Don't touch anything.]*

Hi, I'm Mohamed. Before I show you anything, let me get the awkward question out of the
way.

The brief said pick one track. I did two. So, why.

They're the same thing pointed at two problems. One config file holds the rules, the
rules make every decision, and the model only does the couple of things rules genuinely
can't. And anywhere we didn't measure something, it says so instead of putting a zero
there and hoping nobody asks.

The lead engine is what I'm submitting. The second one is the same argument against a
harder problem, where the answer comes back zero.

Things I decided not to build: per-market queries, live keys for ChatGPT and Perplexity,
and writing back into a CRM.

---

## Lead logic

*[Click **Lead logic**.]*

How it decides, then I'll run it.

One lead, top to bottom. And the number on each step is how many of my five leads got
that far.

Five come in. One drops out straight away because it's a Gmail address, and there's no
company behind a Gmail address, so I don't spend money finding that out. Four go to the
paid lookups. One of those doesn't reconcile, so it goes to a human instead of a score.
Three make it through. You can add the branches up. That's the last real run, not a
drawing of how I'd like it to work.

Blue is rules, purple is the model, and everything that can go wrong on me sits up here,
before anything gets decided.

Now this is the bit I want to tell you about.

Halfway through building this, my Apify account hit its free limit. And the scraper
didn't fail. That's the problem. It came back successful, and the data it handed me was
one row, and that row was the error message.

So my code read it, found no name and no job title, and carried on. And my scorer is
deliberately generous about missing data. If we don't know someone's job title, it
doesn't punish them for it, it just writes down that we don't know.

So that lead came out looking like a normal person we happened not to learn much about.
It got scored. It got routed. And the real reason was that I'd run out of credit.

My billing problem turned into a fact about someone's career. That's the exact thing
this project argues against, so finding it in my own code was not a good morning. It's
fixed now. If a scraper refuses us, the lead goes to a person with the reason attached.

---

## Inbound leads

*[Click **Inbound leads**.]*

Five leads, four different outcomes.

Score's out of 198. Roughly a hundred of that is the company, the rest is what they
actually did, and those are separate gates. A perfect company that's never done anything
still can't reach sales.

*[Expand Satya Nadella.]*

Every point tells you where it came from. And these three, revenue, valuation, funding,
are marked as not scored rather than scored zero. You can't get those for a private
company, and if you ask a model it'll hand you a very confident number it invented.

*[Point at the green chips.]* And the model declares which facts it used. A draft citing
nothing is a mail merge with a name in it.

### Live

*[Type: Judith · Wiese · judith.wiese@siemens.com. Tick assessment + pricing. Click.]*

Let me put someone real through it. That's a work email built from the company's usual
pattern, and the pipeline only uses the domain, because the domain is the one thing here
no search engine suggested to me.

*[SAY NOTHING. ~20 seconds. Then read the steps off the screen.]*

That's the actual trace, written as it happens.

And it reconciles on two things. The company's website has to match the email domain,
and the name on the profile has to match the mailbox.

That second one's there because if you search a name at a company with three hundred
thousand employees, quite often you find a different employee. And a record like that
doesn't score badly. It scores well, because every field is filled in.

Chief People Officer at Siemens, 278,000 people, 122 points, hot. Untick those two
behaviour boxes and she drops to 82 and goes to the warm queue. Big company, right
title, no signal, that's not a hot lead.

---

## AEO logic

*[Click **AEO logic**.]*

Second half. Whether we show up when someone asks an AI assistant.

These two striped paths are what I care about, and they're not the same thing.

Forty of these we never asked. No key for ChatGPT or Perplexity, so I don't have an
answer and I say so. Twenty we did ask, and nothing came back, because my Anthropic
credit ran out mid-run.

Both get filed as not measured, both stay out of the percentages. But if that second
number starts climbing, my tool is broken. If only the first is high, it's just narrower
than I'd like. And letting either show up as "we're not there" would be me reporting my
own missing API key as a fact about the market.

---

## AI visibility

*[Click **AI visibility**.]*

One number, and you can take it apart.

It says one out of ninety, not out of a hundred. One of the four things I score is where
we rank among the brands named, and nothing named us at all, so there's no position to
hold. Rather than score that zero, I take the points out of the total and say why.

*[Benchmark.]* Zero out of ten. A count, not a percentage. Thirty percent looks identical
whether it's three out of ten, or three out of ten with four you never checked.

*[Source gap.]* This is the part I'd act on. Knowing we lose ten questions isn't useful.
Knowing the answers beating us lean on a hundred and two blog roundups, four analyst
pieces and two competitors' own sites tells you exactly where to go.

*[Recommendations.]* The model writes these, then a plain lookup checks every source it
names against what we actually collected.

*[Click "See what winning looks like →".]* Same screen, seeded data. One of ninety
becomes fifty-five out of a hundred. And it tells you it's seeded, because that flag
lives in the database row, not in a caption I could forget to write.

*[Click back. Type a question in the ad-hoc box, click Ask.]* And I can ask one live.

*[SAY NOTHING. ~30 seconds.]*

Real engines, just now. The two without keys say "never called" rather than going quiet.
And this one isn't saved, because those ten questions are fixed, and letting a one-off
write into the same table would ruin every comparison I have.

---

## Close

Cost is measured, not guessed. Six cents a lead, about three dollars a full run.

One thing on tooling. The scraping goes through Apify because I already had an account
and could be running the same afternoon. It's a marketplace of other people's scrapers,
not a data provider, and two of them doing the same job handed back completely different
shapes of data. In production I'd buy the data, not the scraper. And for the visibility
side I'd probably just pay for Otterly at thirty a month. What's worth keeping from mine
is the source gap and the recommendations, because none of them do that.

The scheduled version is built and switched off on purpose. Forty dollars a month to
watch a number that's currently zero. One line to turn on when there's something to
watch.

If I kept going, first thing I'd add is per-market queries. AI answers change by
country, and Europe is the bit this role is actually about.

Thanks for watching.

---

## Reminders

- Two silences are on purpose. Let them run.
- Don't read the screen aloud, and don't say "as you can see".
- Don't apologise for the zero or the missing keys. Say why once, move on.
- If they ask how long it took, tell them the truth.

## Before you record

- Server running **without** `--reload`. Saving a file mid-run kills a collection.
- Run picker on **run 3 · measured**.
- Five leads in the table. Lookups add to it now, so rehearsals stack up —
  `python -m aeo.leads` gives you a clean five.
- Rehearse the exact lookup you'll do on camera.
- Close the Apify and Claude billing tabs.
