# Loom cue cards

Not a script. Glance, say it your way, move.

**Target 6:30.** The big change: **start the lookup, then talk while it runs.** No silence.

---

## 0:00 OPEN — 30s
*[On Inbound leads]*

- Brief said pick one. I did two.
- Same engine, two problems
- One config file. Rules decide. Model only does what rules can't.
- Anything unmeasured says so — never a zero
- **Lead engine is the submission.** Other one's the same argument, harder problem
- Didn't build: per-market queries · ChatGPT+Perplexity keys · CRM write-back

## 0:30 THE TABLE — 40s

- Five leads, four outcomes
- Score out of 198. ~100 company, rest behaviour. **Separate gates.**
- Perfect company, no signal → still can't reach sales

*[Expand Satya]*
- Every point shows its source
- Revenue / valuation / funding = **not scored, not zero**
- Can't get them for private companies. Ask a model, it invents one.
- Green chips = which facts the model used
- Cites nothing → mail merge with a name in it

## 1:10 START THE LOOKUP — then talk
*[Type Judith · Wiese · judith.wiese@siemens.com — tick assessment + pricing — CLICK]*

- "Real person. Work email from the company pattern."
- "Only the domain matters — one fact no search engine gave me."

**Now leave it running and tell this:**

- Halfway through building, Apify hit its free limit
- **Scraper didn't fail. It succeeded.**
- Returned one row. That row was the error message.
- My code read it — no name, no title — and carried on
- My scorer is generous about missing data. Doesn't punish. Writes down "we don't know."
- So it scored. It routed. Looked like a normal lead.
- **Real reason: I'd run out of credit.**
- My billing problem became a fact about someone's career
- Exact thing this project argues against. Found it in my own code.
- Fixed — refused scrape now goes to a human with the reason

## 2:30 READ THE RESULT — 40s

- Point at the rail: "that's the trace, written as it happened"
- Reconciles on **two** things: company website = email domain, **and** name = mailbox
- Why: search a name at a 300,000-person company, you often find someone else
- That record doesn't score badly — **it scores well.** Every field filled in.
- Chief People Officer, Siemens, 278k, **122, hot**
- Untick the two boxes → 82, warm. Right title ≠ buying signal.

## 3:10 LEAD LOGIC — 40s
*[Click Lead logic]*

- Number on each step = how many of the five got that far
- 5 in → 1 out at Gmail (no company, don't spend money) → 4 paid lookups
- 1 doesn't reconcile → human → 3 through
- **Add the branches up.** Last real run, not a drawing.
- Blue = rules. Purple = model. Anything that can break sits above the deciding.

## 3:50 AEO LOGIC — 50s
*[Click AEO logic]*

- Second half: do we show up when someone asks an AI assistant
- **Two striped paths. Not the same claim.**
- 40 we never asked — no keys, and I say so
- 20 we asked, nothing came back — my credit ran out
- Both "not measured", both out of the percentages
- Second number climbing = broken tool. First high = just narrower.
- Letting either read "we're not there" = reporting my own missing API key as a fact about the market

## 4:40 AI VISIBILITY — 90s
*[Click AI visibility]*

- One number, comes apart
- **1 of 90, not 1 of 100** — nothing named us, so no rank to score
- Took those points out rather than scoring zero
- **0 of 10.** Count, not percentage.
- 30% looks the same as 3-of-10-with-4-never-checked

*[Source gap]*
- **This is the part I'd act on**
- Losing ten questions isn't useful
- 43 blog roundups, 3 analyst pieces, 2 competitor sites → that's where to go

*[Recommendations]*
- Model writes them, lookup checks every source against what we collected

*[Click "See what winning looks like"]*
- Seeded data, same screen. **1 of 90 → 55 of 100.**
- Says it's seeded because the flag lives in the row, not a caption
*[Click back]*

**Optional if time — skip if over 5:30:** ask one live, 30s wait

## 6:00 CLOSE — 30s

- Cost measured not guessed. 6c a lead, ~$3 a run.
- Scraping goes through Apify because I had an account and could start that afternoon
- It's a marketplace of other people's scrapers, not a data provider
- Two doing the same job returned different shapes of data
- Production: **buy the data, not the scraper.** Cognism for Europe.
- Visibility side — I'd probably just pay for Otterly, $30/mo
- Worth keeping from mine: the source gap and the recommendations. None of them do that.
- Scheduled version built, switched off. $40/mo to watch a zero. One line to turn on.
- Next thing I'd add: per-market queries. Europe is what this role is about.
- Thanks for watching.

---

## If you're running long

Cut in this order:
1. The live ad-hoc query (30s + wait)
2. Lead logic section entirely (40s) — the funnel is nice, not essential
3. The Otterly/Cognism detail — just say "I'd buy the data, not the scraper"

## Don't

- Don't wait in silence for the lookup — that's what the Apify story is for
- Don't read the screen
- Don't apologise for the zero
