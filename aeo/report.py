"""Standalone HTML export.

The same page the local app serves, with the data baked in — one file, no
server, no keys, opens by double-clicking. The reviewer with fifteen minutes
and no intention of cloning anything sees the whole result; the repo is there
for the reviewer who wants to check the code.

One template, two delivery modes: the page uses `window.__AEO_DATA__` when it
is present and falls back to the API when it is not.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import analyze, config, db
from .config import ROOT
from .engines import ENGINE_LABELS

TEMPLATE = ROOT / "web" / "static" / "index.html"
OUT = ROOT / "out"


# ---------------------------------------------------------------------------
# CONSTRAINT 4 — no scraped personal data leaves this machine.
# ---------------------------------------------------------------------------
#
# This file writes a SHAREABLE artifact. Track A now scrapes real people: names,
# work emails, LinkedIn URLs, job histories, and a drafted email addressed to them by
# name. Embedding that in an HTML file that gets attached to a submission, pasted into
# Slack and left in a Downloads folder is exactly the thing the constraint forbids —
# and it would happen silently, because the export "just works".
#
# So the export REDACTS by default and says that it did. What survives is everything
# needed to judge the method — the score, every point that made it, the routing and
# its reasoning, the reconciliation verdict, the company firmographics — and what goes
# is everything that identifies a human.
#
# Company facts are deliberately kept: a headcount is not personal data, and without it
# the scoring breakdown is unreadable. The email DOMAIN is kept for the same reason
# (it is the reconciliation key and it names a company, not a person); the local part
# is masked.
_PERSONAL = ("name", "email", "linkedin_url", "message", "trace")


def _redact(row: dict) -> dict:
    out = dict(row)
    email = row.get("email") or ""
    domain = email.split("@")[-1] if "@" in email else ""
    out["name"] = "— redacted —"
    out["email"] = f"•••@{domain}" if domain else "— redacted —"
    out["linkedin_url"] = None
    # The draft is the single most identifying field: it is addressed to them by name
    # and quotes their record back. The COUNT of facts it cited survives, which is what
    # the "is this a mail-merge" check actually needs.
    out["message"] = ("— draft redacted from the export. It cited "
                      f"{len(row.get('evidence') or [])} specific facts from the record; "
                      "run the app locally to read it.") if row.get("message") else None
    out["trace"] = []
    return out


def _leads_payload(include_personal: bool = False) -> dict:
    """Track A, so the export carries both tracks and the reviewer can switch."""
    from . import leads as L
    fit = L.load_fit()
    with db.session() as conn:
        lrid = db.latest_lead_run_id(conn)
        if lrid is None:
            return {"empty": True}
        rows = db.leads(conn, lrid)
        run = db.lead_run(conn, lrid)
    for r in rows:
        r["intent"] = L.intent_points(r["breakdown"])
    summary = L.summarise(rows)
    if not include_personal:
        rows = [_redact(r) for r in rows]
    return {"empty": False, "run": run, "leads": rows,
            "summary": summary, "routing": fit.routing,
            "method": fit.method(), "stale_fit": False,
            "redacted": not include_personal}


def build_payload(include_personal: bool = False,
                  with_recommendations: bool = False) -> dict:
    cfg = config.load()
    leads_payload = _leads_payload(include_personal)
    with db.session() as conn:
        rid = db.latest_run_id(conn)
        runs = db.runs(conn)
        if rid is None:
            return {"report": {"empty": True}, "trend": [], "config": {},
                    "leads": leads_payload}

        run = next((r for r in runs if r["id"] == rid), None)
        obs = db.observations(conn, rid)
        cits = db.citations(conn, rid)
        comps = db.competitors(conn, rid)

        trend = []
        for r in runs:
            s = analyze.summarise(
                db.observations(conn, r["id"]),
                db.citations(conn, r["id"]),
                db.competitors(conn, r["id"]),
            )
            trend.append({
                "run_id": r["id"], "at": r["started_at"],
                "synthetic": bool(r["is_synthetic"]),
                "comparable": r.get("query_set_hash") == cfg.query_set_hash,
                "presence_rate": s["presence_rate"],
                "cited_rate": s["cited_rate"],
                "citation_share": s["citation_share"],
            })

    cells: dict[str, dict] = defaultdict(lambda: {"runs": [], "live": True, "note": None})
    for o in obs:
        c = cells[f"{o['query_id']}|{o['engine']}"]
        c["runs"].append(o["status"])
        c["live"] = c["live"] and bool(o["is_live"])
        if not o["is_live"] and not c["note"]:
            c["note"] = o.get("answer_excerpt")
        c["error"] = o.get("error")

    grid = [
        {"query_id": k.split("|")[0], "engine": k.split("|")[1],
         "statuses": v["runs"], "live": v["live"], "note": v["note"],
         "error": v.get("error"), "stable": len(set(v["runs"])) == 1}
        for k, v in cells.items()
    ]

    # Same derived views the live API serves, so the export is not a lesser page.
    import json as _json
    serp_by_q: dict[str, set] = defaultdict(set)
    cited_by_q: dict[str, set] = defaultdict(set)
    for o in obs:
        try:
            for dmn in _json.loads(o.get("serp_domains") or "[]"):
                serp_by_q[o["query_id"]].add(dmn)
        except (TypeError, ValueError):
            pass
    for c in cits:
        if c.get("domain"):
            cited_by_q[c["query_id"]].add(c["domain"])
    seo_rows = [{"query_id": q, "cited_domains": sorted(cited_by_q.get(q, ())),
                 "serp_domains": sorted(v)} for q, v in serp_by_q.items() if v]

    bench = analyze.benchmark(obs, cfg)
    gap = analyze.source_gap(obs, cits, comps, cfg)
    seo = analyze.seo_overlap(seo_rows)
    summary = analyze.summarise(obs, cits, comps)

    # Baked in at export time, because the standalone file has no server to ask and a
    # "Generate" button over file:// would be a control that cannot work. Costs one
    # model call, so it is opt-in.
    recs = None
    if with_recommendations:
        from . import recommend
        recs = recommend.build(bench, gap, seo, summary, cfg)

    return {
        "leads": leads_payload,
        "recommendations": recs,
        "report": {
            "empty": False,
            "run": run,
            "summary": summary,
            "benchmark": bench,
            "score": analyze.score(bench, summary, obs, cfg),
            "source_gap": gap,
            "seo": seo,
            "grid": grid,
            "queries": [{"id": q.id, "text": q.text, "intent": q.intent,
                         "benchmark": q.benchmark} for q in cfg.queries],
            "engines": [{"key": k, "label": ENGINE_LABELS.get(k, k)}
                        for k in ENGINE_LABELS if cfg.engine_enabled(k)],
            "brand": cfg.brand_name,
            "stale_contract": False,
        },
        "trend": trend,
        "config": {"brand": cfg.brand_name, "query_set_hash": cfg.query_set_hash},
    }


def export(path: Path | None = None, include_personal: bool = False,
           with_recommendations: bool = False) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = path or (OUT / "aeo_report.html")

    html = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(build_payload(include_personal, with_recommendations),
                      ensure_ascii=False)
    # </script> inside JSON would close the tag early.
    blob = blob.replace("</", "<\\/")
    html = html.replace(
        "<!--EMBED-->",
        f'<script>window.__AEO_DATA__ = {blob};</script>',
    )
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Write the standalone HTML report.")
    ap.add_argument(
        "--include-personal", action="store_true",
        help="Embed scraped names, emails, profile URLs and drafted messages. OFF by "
             "default: this file is meant to be shared, and Track A holds real people. "
             "Only pass this for a local demo whose leads you know are public figures.")
    ap.add_argument(
        "--with-recommendations", action="store_true",
        help="Also write the 3-5 AEO recommendations into the file. Costs one model "
             "call. The standalone export has no server to generate them on demand.")
    a = ap.parse_args()
    p = export(include_personal=a.include_personal,
               with_recommendations=a.with_recommendations)
    print(p)
    print("personal fields EMBEDDED — do not share this file"
          if a.include_personal else
          "personal fields redacted (names, emails, profile URLs, drafts)")
