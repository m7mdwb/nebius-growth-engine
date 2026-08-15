# **Growth Marketing Engineer (B2B) — Take-Home Assignment**

### **Context**

At Nebius Academy we help organizations adopt AI through training — combining tailored programs, data-driven pre-training assessments, and expert-led instruction. This role reports to the CMO and exists to build the demand generation engine: AI-powered growth systems, automated workflows, and experimentation infrastructure that let us launch and optimize go-to-market at speed.

This assignment reflects the actual work. We're less interested in a polished strategy deck and more interested in seeing you *build something that runs*. A rough prototype that works beats a beautiful plan that doesn't.

**Time:** Please cap this at \~4 hours (don't exceed 5). If you run out of time, ship what you have and tell us what you'd do next — we'd rather see scope judgment than heroics.

**Use AI freely.** This is an AI-native role. We *expect* you to use Claude, ChatGPT, agent frameworks, Cursor, whatever you reach for day to day. How you use them is part of what we're evaluating.

**Make assumptions.** You don't have access to our internal systems or data. Where you'd normally pull real numbers or CRM records, use realistic mock data and state the assumption. We're evaluating your thinking and your build, not your access.

---

### **The scenario**

Nebius Academy runs an **AI Readiness Assessment** — a short diagnostic that helps enterprise L\&D and leadership teams understand where they stand on AI adoption, and positions us as a strategic partner rather than a training vendor. It's a top-of-funnel lead magnet promoted across LinkedIn, Google, and Meta.

Right now the funnel is manual: leads come in, someone eventually looks at them, and follow-up is inconsistent and slow. We want to fix that with systems, not headcount.

---

### **Your task**

Pick **one** of the three tracks below and build a working prototype. Choose the one that lets you show your strongest work — we don't score tracks differently.

You can use any stack: Zapier, Make, n8n, Gumloop, Clay, custom code (Python/JS), or a combination. If a piece can't fully run in the time available, mock that piece and clearly mark the seam.

#### **Track A — Inbound lead engine**

Build a workflow that takes a raw inbound lead (e.g. someone who completed the AI Readiness Assessment or registered for a webinar) and:

* enriches it (company, size, industry, role seniority — real enrichment tool or mocked),  
* scores or qualifies it against a fit definition you design,  
* routes it (e.g. MQL to nurture vs. hot lead to Sales), and  
* drafts a genuinely personalized first-touch message, not a mail-merge with a `{{first_name}}`.

Run it end-to-end on 3–5 sample leads and show the outputs.

#### **Track B — Campaign production agent (the "AI army")**

Build an agent or workflow that takes a single input — a product page, one-pager, or short brief (we suggest using one of our products: **Skillcheck**, the **AI Learning Platform**, or **Evolve**) — and produces a coordinated mini-campaign:

* LinkedIn ad copy (2–3 variants),  
* Google Search ad copy (2–3 variants),  
* one nurture email, and  
* a landing-page hero section (headline \+ subhead \+ CTA).

Include a review/approval step so a human can steer it — an agent that a marketer can actually trust in production. Show it running on one real product.

#### **Track C — Agent Engine Optimization (AEO)**

Build a workflow that measures and improves how Nebius Academy shows up inside AI assistants and generative search. It should:

* query several assistants (Claude, ChatGPT, Perplexity, Google AI, etc.) with buyer-intent prompts like *"best AI readiness training for enterprises"* or *"how do we upskill our team on AI,"*  
* capture whether and how we appear, and who appears instead,  
* structure the findings into something comparable over time, and  
* output 3–5 concrete AEO recommendations.

Bonus: make the monitoring recurring rather than a one-off run.

---

### **For every track, also tell us (briefly)**

1. **How you'd measure impact.** What's the metric, what's the baseline, how would you know it's working?  
2. **How you'd scale it.** What breaks if volume goes 10×, and what would you build next?  
3. **One tradeoff you made** because of the time limit, and what the production version would do differently.

Keep this to roughly one page — bullets are fine.

---

### **What to submit**

* **A short walkthrough (5–8 min Loom or similar)** showing the prototype actually running. This is the most important artifact — it lets us see the real thing, not screenshots.  
* **The build itself:** a link to the workflow / repo / shared canvas, plus any config or prompts. Read access is fine.  
* **A one-page summary** covering the three questions above.

No slide deck required. If you'd rather answer the three questions inside the Loom than write them up, that's fine too.

Questions during the assignment are welcome — reach out to Laure Faretti. Asking a sharp clarifying question is a positive signal, not a weakness.

