"""Track C — turn the source gap into 3–5 concrete AEO recommendations.

Same division of labour as Track A, for the same reason:

    RULES ASSEMBLE THE EVIDENCE.  THE MODEL WRITES THE RECOMMENDATION.

Everything the model is shown here is computed: which of the ten queries we lost,
which domains the winning answers cited, what kind of source each of those is, and
whether the AI-cited domains were also ranking organically. None of that is inferred.
Ask a model to "analyse our AEO performance" against raw answers and it will produce
five confident, generic, unfalsifiable bullets — *publish more thought leadership*,
*build topical authority* — that would be identical for any company in any category.
Handing it a table it cannot argue with is what makes the output specific.

⚠️ And it is told what it does NOT know. A recommendation engine that cannot see the
edges of its evidence will happily recommend acting on things nobody measured.
"""

from __future__ import annotations

import json

from .config import Config, env

_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string",
                              "description": "The action, as an imperative. Six to ten words."},
                    "why": {"type": "string",
                            "description": "The reasoning, citing the specific numbers given."},
                    "evidence": {
                        "type": "array", "items": {"type": "string"},
                        "description": "The exact data points from the brief this rests on.",
                    },
                    "effort": {"type": "string", "enum": ["low", "medium", "high"]},
                    "horizon": {"type": "string", "enum": ["weeks", "months", "quarters"]},
                    "measure_with": {
                        "type": "string",
                        "description": "Which number on this dashboard would move if it worked.",
                    },
                },
                "required": ["title", "why", "evidence", "effort", "horizon", "measure_with"],
                "additionalProperties": False,
            },
        },
        "seo_verdict": {
            "type": "string",
            "description": "Does SEO feed AEO here, on THIS evidence? Say if it is too thin.",
        },
    },
    "required": ["recommendations", "seo_verdict"],
    "additionalProperties": False,
}

_PROMPT = """You are advising Nebius Academy on Agent Engine Optimization — how their \
brand appears inside AI assistants and generative search. They sell an enterprise AI \
learning platform: a customised, partly AI-delivered training environment with human \
instructors, sold per-client as a solution. Not a course catalogue.

Everything below was MEASURED by the tool. Nothing here is an estimate.

## The benchmark
We appear in {appear_in} of {out_of} buyer-intent queries. Target is {out_of} of {out_of}.
Of those appearances, {cited} earned a citation (a link) and {mentioned} were name-only \
mentions with no link.

## The queries we lost
{lost}

## What the answers that beat us cite instead, by kind of source
{kinds}

## Per-query detail on the lost queries
{per_query}

## Does SEO feed AEO — measured on this run
{seo}

## What we did NOT measure
{gaps}

---

Write 3 to 5 recommendations.

Rules:
- Every recommendation must rest on a number ABOVE, quoted in `evidence`. If you cannot \
point at the data, do not make the recommendation.
- Be specific to the source types that actually appear. "Get listed on G2" is a \
recommendation; "build topical authority" is not, and would read identically for any \
company in any market — if a sentence would survive being pasted into a competitor's \
report, delete it.
- 🔑 The most valuable finding in this category is usually that the lever is NOT the \
brand's own website. AI answers ground on third-party sources, so if the winning \
citations are review platforms, roundups or competitor blogs, say so plainly and say \
what to do about it — that is closer to digital PR than to on-site SEO.
- Distinguish CITED from MENTIONED where it matters. Being named with no link and \
being named with a link need different fixes.
- `measure_with` must name a number this dashboard already reports: the N-of-10 count, \
citation share, the competitor set, or the cited-domain ranking.
- For `seo_verdict`, answer only from the overlap figure given. If the sample is too \
small to support a verdict, say that instead of picking one — a confident answer from \
three data points is worse than no answer.
- Do not recommend anything whose effect could not be seen in a re-run of this tool."""


def _fmt_kinds(gap: dict) -> str:
    if not gap.get("kinds"):
        return "(no citations recorded on the lost queries)"
    out = []
    for k in gap["kinds"]:
        doms = ", ".join(f"{d['domain']} ({d['n']})" for d in k["top_domains"])
        out.append(f"- {k['label']}: {k['citations']} citations across the lost queries. "
                   f"{'WE APPEAR HERE.' if k['we_appear'] else 'We do not appear here.'} "
                   f"Top: {doms}")
    return "\n".join(out)


def _fmt_per_query(gap: dict) -> str:
    if not gap.get("per_query"):
        return "(none)"
    out = []
    for q in gap["per_query"][:10]:
        doms = ", ".join(f"{d['domain']}" for d in q["domains"][:6])
        out.append(f'- "{q["query"]}" -> cites: {doms}')
    return "\n".join(out)


def build(bench: dict, gap: dict, seo: dict, summary: dict, cfg: Config) -> dict:
    """Assemble the evidence, ask for the recommendations, return them.

    Returns {recommendations: [...], seo_verdict, error?}. A failure is a marked seam
    like everything else — the measured half of the page still stands on its own.
    """
    key = env("ANTHROPIC_API_KEY")
    if not key:
        return {"recommendations": [], "seo_verdict": None,
                "error": "SEAM: no ANTHROPIC_API_KEY — the benchmark and the source gap "
                         "above are measured and unaffected; only the written "
                         "recommendations are missing."}

    import anthropic

    lost = "\n".join(f'- "{r["query"]}" ({r["intent"]})' for r in bench.get("lost", []))
    gaps = []
    if bench.get("unmeasured"):
        gaps.append(f"{len(bench['unmeasured'])} of the {bench['out_of']} queries were "
                    f"NOT measured on this run ({', '.join(bench['unmeasured'])}) — they "
                    f"are excluded from the count, not scored as losses.")
    seams = [e for e, v in (summary.get("by_engine") or {}).items() if not v.get("n")]
    gaps.append("ChatGPT and Perplexity are declared seams on this account — no key. "
                "Two of four surfaces are unmeasured, so the count reflects Claude and "
                "Google AI Overviews only.")
    if (seo.get("queries_compared") or 0) < 3:
        gaps.append(f"The SEO/AEO overlap is computed from only "
                    f"{seo.get('queries_compared', 0)} queries — too thin for a verdict.")

    prompt = _PROMPT.format(
        appear_in=bench.get("appear_in", 0), out_of=bench.get("out_of", 0),
        cited=bench.get("cited", 0), mentioned=bench.get("mentioned", 0),
        lost=lost or "(none — we appear in every measured query)",
        kinds=_fmt_kinds(gap), per_query=_fmt_per_query(gap),
        seo=json.dumps({k: v for k, v in seo.items() if k != "detail"}, indent=1),
        gaps="\n".join(f"- {g}" for g in gaps),
    )

    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.messages.create(
            model=cfg.raw.get("recommendations", {}).get("model", "claude-opus-5"),
            max_tokens=int(cfg.raw.get("recommendations", {}).get("max_tokens", 3000)),
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"recommendations": [], "seo_verdict": None,
                "error": f"{type(exc).__name__}: {exc}"}

    if getattr(resp, "stop_reason", None) == "max_tokens":
        return {"recommendations": [], "seo_verdict": None,
                "error": "recommendations hit max_tokens and were truncated"}

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        return {"recommendations": [], "seo_verdict": None,
                "error": "recommendations were not valid JSON", "raw": text[:400]}
    out["error"] = None
    return out
