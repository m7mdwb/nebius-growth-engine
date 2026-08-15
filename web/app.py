"""Local dashboard.

    uvicorn web.app:app --reload   ->   http://127.0.0.1:8000

Deliberately a single-page app with no build step: FastAPI serves one HTML file
and a handful of JSON endpoints. `pip install -r requirements.txt` then one
command is the whole setup, which matters when someone else has to run it.

Collection runs on a background thread and the page polls for progress, so the
"pull live data" button in a walkthrough is doing exactly what it appears to do.
"""

from __future__ import annotations

import sys
import threading
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeo import analyze, config, db, report  # noqa: E402
from aeo.engines import ENGINE_LABELS  # noqa: E402

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="AEO monitor")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Progress for the running collection. One run at a time by design — this is a
# local tool, and a queue would be scaffolding nobody needs.
_state: dict = {"running": False, "log": [], "step": 0, "steps": 0, "run_id": None}
_lock = threading.Lock()


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def api_config() -> JSONResponse:
    cfg = config.load()
    return JSONResponse({
        "brand": cfg.brand_name,
        "query_set_hash": cfg.query_set_hash,
        "queries": [{"id": q.id, "text": q.text, "intent": q.intent,
                     "benchmark": q.benchmark} for q in cfg.queries],
        "engines": [
            {"key": k, "label": ENGINE_LABELS.get(k, k), "live": cfg.engine_live(k)}
            for k in ENGINE_LABELS if cfg.engine_enabled(k)
        ],
        "repeats": cfg.repeats,
        "repeat_subset": cfg.repeat_subset,
        "keys": key_status(),
    })


def key_status() -> list[dict]:
    """Which credentials are present, and what stops working without each.

    ⚠️ Presence ONLY. The value is never returned, never logged and never rendered —
    the page reports that a key exists, which is all anyone needs to know why an
    engine is a seam. Anything more would put a live credential in a browser tab and
    in every screen recording of this dashboard.
    """
    import os
    rows = [
        ("ANTHROPIC_API_KEY", "Claude engine, lead drafting, recommendations"),
        ("APIFY_TOKEN", "Google AI Overviews, LinkedIn person + company enrichment"),
        ("SERPER_API_KEY", "Finds the LinkedIn profile behind a name and email"),
        ("OPENAI_API_KEY", "ChatGPT engine — absent, so it is a declared seam"),
        ("PERPLEXITY_API_KEY", "Perplexity engine — absent, so it is a declared seam"),
    ]
    return [{"name": n, "present": bool(os.getenv(n)), "unlocks": what}
            for n, what in rows]


@app.get("/api/runs")
def api_runs() -> JSONResponse:
    with db.session() as conn:
        return JSONResponse(db.runs(conn))


@app.get("/api/report")
def api_report(run_id: int | None = None) -> JSONResponse:
    cfg = config.load()
    with db.session() as conn:
        rid = run_id or db.latest_run_id(conn)
        if rid is None:
            return JSONResponse({"empty": True})

        run = next((r for r in db.runs(conn) if r["id"] == rid), None)
        obs = db.observations(conn, rid)
        cits = db.citations(conn, rid)
        comps = db.competitors(conn, rid)

    summary = analyze.summarise(obs, cits, comps)

    # Grid: one cell per query x engine. A cell holds every repeat, so the UI
    # can show disagreement rather than hiding it behind a majority vote.
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
         "error": v.get("error"),
         "stable": len(set(v["runs"])) == 1}
        for k, v in cells.items()
    ]

    queries = [{"id": q.id, "text": q.text, "intent": q.intent,
                "benchmark": q.benchmark} for q in cfg.queries]
    engines = [{"key": k, "label": ENGINE_LABELS.get(k, k)}
               for k in ENGINE_LABELS if cfg.engine_enabled(k)]

    # The benchmark, the source gap and the SEO overlap are all DERIVED — computed
    # from the stored observations on every request rather than written down at
    # collection time. That way changing the classification rules re-reads history
    # instead of requiring a re-run, which at these prices matters.
    bench = analyze.benchmark(obs, cfg)
    gap = analyze.source_gap(obs, cits, comps, cfg)
    seo = analyze.seo_overlap(_seo_rows(obs, cits))

    return JSONResponse({
        "empty": False,
        "run": run,
        "summary": summary,
        "benchmark": bench,
        "source_gap": gap,
        "seo": seo,
        "grid": grid,
        "queries": queries,
        "engines": engines,
        "brand": cfg.brand_name,
        "stale_contract": bool(run and run.get("query_set_hash")
                               and run["query_set_hash"] != cfg.query_set_hash),
    })


def _seo_rows(obs: list[dict], cits: list[dict]) -> list[dict]:
    """Pair up, per query, the domains the AI answer CITED against the domains
    ranking organically underneath it."""
    import json as _json
    serp: dict[str, set] = defaultdict(set)
    for o in obs:
        try:
            for d in _json.loads(o.get("serp_domains") or "[]"):
                serp[o["query_id"]].add(d)
        except (TypeError, ValueError):
            continue
    cited: dict[str, set] = defaultdict(set)
    for c in cits:
        if c.get("domain"):
            cited[c["query_id"]].add(c["domain"])
    return [{"query_id": q, "cited_domains": sorted(cited.get(q, ())),
             "serp_domains": sorted(v)} for q, v in serp.items() if v]


@app.get("/api/recommendations")
def api_recommendations(run_id: int | None = None) -> JSONResponse:
    """3–5 concrete AEO recommendations, written from the measured evidence.

    A separate endpoint from /api/report on purpose: this one costs a model call, and
    the measured half of the page must render instantly and for free. If the
    recommendations fail, the benchmark and the source gap are still on screen.
    """
    from aeo import recommend

    cfg = config.load()
    with db.session() as conn:
        rid = run_id or db.latest_run_id(conn)
        if rid is None:
            return JSONResponse({"empty": True})
        obs, cits = db.observations(conn, rid), db.citations(conn, rid)
        comps = db.competitors(conn, rid)

    out = recommend.build(
        analyze.benchmark(obs, cfg),
        analyze.source_gap(obs, cits, comps, cfg),
        analyze.seo_overlap(_seo_rows(obs, cits)),
        analyze.summarise(obs, cits, comps),
        cfg,
    )
    return JSONResponse({"empty": False, "run_id": rid, **out})


@app.post("/api/adhoc")
def api_adhoc(payload: dict) -> JSONResponse:
    """Ask one query live, right now, and show what comes back.

    ⚠️ NOT persisted into the benchmark tables, and that is the whole design of this
    endpoint. The ten queries are a fixed measurement contract — a trend line only
    means anything if the question set behind it did not move — so letting an ad-hoc
    query write into the same tables would corrupt every comparison to date for the
    sake of one curious lookup. It runs, it renders, it is gone.
    """
    from aeo.engines import ENGINES

    q = (payload or {}).get("query", "").strip()
    if not q:
        return JSONResponse({"error": "no query"}, status_code=400)

    cfg = config.load()
    out = []
    for name in [n for n in ENGINES if cfg.engine_enabled(n)]:
        res = ENGINES[name](q, cfg)
        obs = analyze.classify(res, cfg)
        out.append({
            "engine": name, "label": ENGINE_LABELS.get(name, name),
            "live": bool(res.is_live), "status": obs["status"],
            "note": obs.get("note"), "error": obs.get("error"),
            "answer": (res.answer or "")[:2500],
            "citations": obs["citations"],
            "competitors": obs["competitors"],
        })
    return JSONResponse({"query": q, "results": out, "persisted": False})


@app.get("/api/trend")
def api_trend() -> JSONResponse:
    """Presence and citation share across runs.

    Synthetic runs are returned WITH their flag, never merged into the real
    series. The chart draws them differently; the data keeps them apart.
    """
    cfg = config.load()
    points = []
    with db.session() as conn:
        for r in db.runs(conn):
            s = analyze.summarise(
                db.observations(conn, r["id"]),
                db.citations(conn, r["id"]),
                db.competitors(conn, r["id"]),
            )
            points.append({
                "run_id": r["id"],
                "at": r["started_at"],
                "synthetic": bool(r["is_synthetic"]),
                "comparable": r.get("query_set_hash") == cfg.query_set_hash,
                "presence_rate": s["presence_rate"],
                "cited_rate": s["cited_rate"],
                "citation_share": s["citation_share"],
            })
    return JSONResponse(points)


@app.post("/api/run")
def api_run() -> JSONResponse:
    with _lock:
        if _state["running"]:
            return JSONResponse({"started": False, "reason": "a run is already going"})
        _state.update(running=True, log=[], step=0, steps=0, run_id=None)

    def progress(ev: dict) -> None:
        with _lock:
            if ev["event"] == "run_started":
                _state["steps"] = ev["steps"]
                _state["run_id"] = ev["run_id"]
            elif ev["event"] == "result":
                _state["step"] = ev["step"]
                _state["log"].append(ev)

    def worker() -> None:
        from aeo.run import collect
        try:
            collect(label="manual", on_progress=progress)
        except Exception as exc:  # noqa: BLE001 - surface it, don't swallow it
            with _lock:
                _state["log"].append({"event": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            with _lock:
                _state["running"] = False

    threading.Thread(target=worker, daemon=True).start()
    return JSONResponse({"started": True})


@app.get("/api/status")
def api_status() -> JSONResponse:
    with _lock:
        return JSONResponse({
            "running": _state["running"],
            "step": _state["step"],
            "steps": _state["steps"],
            "run_id": _state["run_id"],
            "log": _state["log"][-60:],
        })


@app.post("/api/export")
def api_export() -> JSONResponse:
    path = report.export()
    return JSONResponse({"path": str(path)})


# --------------------------------------------------------------------------
# Track A
# --------------------------------------------------------------------------

@app.get("/api/leads")
def api_leads() -> JSONResponse:
    from aeo import leads as L
    fit = L.load_fit()
    with db.session() as conn:
        rid = db.latest_lead_run_id(conn)
        if rid is None:
            return JSONResponse({"empty": True})
        run = db.lead_run(conn, rid)
        rows = db.leads(conn, rid)

    for r in rows:
        r["intent"] = L.intent_points(r["breakdown"])

    return JSONResponse({
        "empty": False,
        "run": run,
        "leads": rows,
        "summary": L.summarise(rows),
        "routing": fit.routing,
        "method": fit.method(),
        "stale_fit": bool(run and run.get("fit_hash") and run["fit_hash"] != fit.fit_hash),
    })


@app.post("/api/leads/run")
def api_leads_run() -> JSONResponse:
    with _lock:
        if _state["running"]:
            return JSONResponse({"started": False, "reason": "a run is already going"})
        _state.update(running=True, log=[], step=0, steps=0, run_id=None)

    def progress(ev: dict) -> None:
        with _lock:
            if ev["event"] == "run_started":
                _state["steps"] = ev["steps"]
                _state["run_id"] = ev["run_id"]
            elif ev["event"] == "result":
                _state["step"] = ev["step"]
                _state["log"].append({
                    "event": "result", "step": ev["step"], "steps": ev["steps"],
                    "engine": ev["route"], "status": f"score {ev['score']}",
                    "citations": 1 if ev["drafted"] else 0,
                    "query": ev["email"], "live": ev["drafted"],
                })

    def worker() -> None:
        from aeo import leads as L
        try:
            L.collect(on_progress=progress)
        except Exception as exc:  # noqa: BLE001
            with _lock:
                _state["log"].append({"event": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            with _lock:
                _state["running"] = False

    threading.Thread(target=worker, daemon=True).start()
    return JSONResponse({"started": True})


@app.post("/api/leads/one")
def api_lead_one(payload: dict) -> JSONResponse:
    """Type a real person in; get a real, looked-up, scored, routed, drafted lead out.

    🔑 This goes through `leads.collect()` with a one-item list — the SAME code path as
    the batch run, not a parallel implementation of it. A form that ran its own copy of
    the pipeline would drift from the batch one within a week, and the demo would stop
    being evidence about the thing that actually runs.

    Intent signals are optional checkboxes rather than a hidden default. A lead typed
    in cold has no first-party behaviour, and therefore cannot clear the intent gate
    however good the firmographics are — which is the gate working. Tick `booked_demo`
    on the same person and watch it go hot.
    """
    from aeo import leads as L

    p = payload or {}
    email = (p.get("email") or "").strip()
    if "@" not in email:
        return JSONResponse({"error": "a work email address is required — the domain is "
                                      "the only fact the reconciliation check can trust"},
                            status_code=400)

    lead = {
        "email": email,
        "first_name": (p.get("first_name") or "").strip(),
        "last_name": (p.get("last_name") or "").strip(),
        "source": p.get("source") or "manual_lookup",
        "signals": [s for s in (p.get("signals") or []) if s],
        "note": (p.get("note") or "").strip() or None,
    }

    with _lock:
        if _state["running"]:
            return JSONResponse({"started": False, "reason": "a run is already going"})
        _state.update(running=True, log=[], step=0, steps=1, run_id=None)

    def progress(ev: dict) -> None:
        with _lock:
            if ev["event"] == "run_started":
                _state["steps"], _state["run_id"] = ev["steps"], ev["run_id"]
            elif ev["event"] == "result":
                _state["step"] = ev["step"]

    try:
        run_id = L.collect(on_progress=progress, samples=[lead])
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)
    finally:
        with _lock:
            _state["running"] = False

    with db.session() as conn:
        rows = db.leads(conn, run_id)
    for r in rows:
        r["intent"] = L.intent_points(r["breakdown"])
    return JSONResponse({"run_id": run_id, "lead": rows[0] if rows else None})
