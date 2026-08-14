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


def build_payload() -> dict:
    cfg = config.load()
    with db.session() as conn:
        rid = db.latest_run_id(conn)
        runs = db.runs(conn)
        if rid is None:
            return {"report": {"empty": True}, "trend": [], "config": {}}

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

    return {
        "report": {
            "empty": False,
            "run": run,
            "summary": analyze.summarise(obs, cits, comps),
            "grid": grid,
            "queries": [{"id": q.id, "text": q.text, "intent": q.intent} for q in cfg.queries],
            "engines": [{"key": k, "label": ENGINE_LABELS.get(k, k)}
                        for k in ENGINE_LABELS if cfg.engine_enabled(k)],
            "brand": cfg.brand_name,
            "stale_contract": False,
        },
        "trend": trend,
        "config": {"brand": cfg.brand_name, "query_set_hash": cfg.query_set_hash},
    }


def export(path: Path | None = None) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = path or (OUT / "aeo_report.html")

    html = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(build_payload(), ensure_ascii=False)
    # </script> inside JSON would close the tag early.
    blob = blob.replace("</", "<\\/")
    html = html.replace(
        "<!--EMBED-->",
        f'<script>window.__AEO_DATA__ = {blob};</script>',
    )
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    print(export())
