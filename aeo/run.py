"""The collector.

Walks queries x engines x repeats, classifies each answer, writes to SQLite.
Takes an optional progress callback so the web app can narrate a live run
during a demo without the collector knowing anything about HTTP.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

from . import analyze, config, db, pricing
from .engines import ENGINES

Progress = Callable[[dict], None]


def _noop(_: dict) -> None:
    pass


def collect(cfg: config.Config | None = None, *, label: str = "manual",
            on_progress: Progress = _noop, limit: int | None = None,
            only_engine: str | None = None, queries: list | None = None) -> int:
    """Walk queries x engines x repeats and store every answer.

    `limit` and `only_engine` exist so the pipeline can be exercised for a few cents
    while it is being changed. ⚠️ A limited run writes a real run row, and its
    benchmark is therefore genuinely "N of 10 with 7 unmeasured" — which the benchmark
    reports rather than hides. Do not use one as a headline figure.
    """
    cfg = cfg or config.load()

    engine_names = [n for n in ENGINES if cfg.engine_enabled(n)
                    and (only_engine is None or n == only_engine)]
    qs = queries if queries is not None else cfg.queries
    if limit:
        qs = qs[:limit]
    units = [(q, cfg.repeats_for(q)) for q in qs]
    total_steps = sum(r for _, r in units) * len(engine_names)

    with db.session() as conn:
        run_id = db.start_run(
            conn,
            label=label,
            query_set_hash=cfg.query_set_hash,
            engines=",".join(engine_names),
        )
        on_progress({"event": "run_started", "run_id": run_id, "steps": total_steps})

        step, spent = 0, 0.0
        for query, repeats in units:
            for engine_name in engine_names:
                fn = ENGINES[engine_name]
                for n in range(1, repeats + 1):
                    step += 1
                    on_progress({
                        "event": "step",
                        "step": step,
                        "steps": total_steps,
                        "query": query.text,
                        "engine": engine_name,
                        "repeat": n,
                    })

                    result = fn(query.text, cfg)
                    obs = analyze.classify(result, cfg)

                    db.record_observation(conn, run_id, {
                        "query_id": query.id,
                        "query_text": query.text,
                        "intent": query.intent,
                        "engine": engine_name,
                        "is_live": 1 if result.is_live else 0,
                        "repeat_n": n,
                        "status": obs["status"],
                        "brand_rank": obs["brand_rank"],
                        "answer_chars": obs["answer_chars"],
                        "answer_excerpt": obs["answer_excerpt"] or obs.get("note"),
                        "error": obs["error"],
                        "serp_domains": obs.get("serp_domains") or [],
                        "usage": result.usage,
                        "cost_usd": pricing.cost_usd(result.usage) if result.usage else None,
                    })
                    spent += pricing.cost_usd(result.usage) if result.usage else 0.0
                    if obs["citations"]:
                        db.record_citations(conn, run_id, [
                            {**c, "query_id": query.id, "engine": engine_name, "repeat_n": n}
                            for c in obs["citations"]
                        ])
                    if obs["competitors"]:
                        db.record_competitors(conn, run_id, [
                            {**c, "query_id": query.id, "engine": engine_name, "repeat_n": n}
                            for c in obs["competitors"]
                        ])

                    # Commit per observation, not once at the end. A full run is
                    # minutes of network calls; holding it in one transaction
                    # means a Ctrl-C, a dropped connection or a killed process
                    # throws away everything collected so far. Found the hard
                    # way when a broken pipe silently discarded a 92-step run.
                    conn.commit()

                    on_progress({
                        "event": "result",
                        "step": step,
                        "steps": total_steps,
                        "query": query.text,
                        "engine": engine_name,
                        "repeat": n,
                        "status": obs["status"],
                        "live": bool(result.is_live),
                        "citations": len(obs["citations"]),
                        # Running total, so spend is legible WHILE the run happens
                        # rather than after it. An 80-step run that dies on an
                        # exhausted balance should say so at call one.
                        "spent_usd": round(spent, 4),
                    })

        db.finish_run(conn, run_id)

    on_progress({"event": "run_finished", "run_id": run_id})
    return run_id


def main() -> int:
    ap = argparse.ArgumentParser(description="Run one AEO collection.")
    ap.add_argument("--label", default="manual", help="run label, e.g. scheduled")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--limit", type=int, help="only the first N queries (cheap test run)")
    ap.add_argument("--engine", help="only this engine, e.g. claude")
    args = ap.parse_args()

    def echo(ev: dict) -> None:
        if args.quiet:
            return
        if ev["event"] == "run_started":
            print(f"run {ev['run_id']}: {ev['steps']} steps", flush=True)
        elif ev["event"] == "result":
            flag = "" if ev["live"] else "  [seam]"
            print(f"  [{ev['step']:>3}/{ev['steps']}] {ev['engine']:<14} "
                  f"{ev['status']:<9} {ev['citations']:>2} cites  "
                  f"${ev.get('spent_usd', 0):>6.3f}  "
                  f"{ev['query'][:40]}{flag}", flush=True)

    run_id = collect(label=args.label, on_progress=echo,
                     limit=args.limit, only_engine=args.engine)

    with db.session() as conn:
        c = db.run_cost(conn, run_id)
    print(f"\ndone. run_id={run_id}")
    print(f"cost: ${c['usd']:.4f} over {c['calls']} billed call(s) — "
          f"{c['inp']:,} in / {c['out']:,} out tokens, {c['searches']} web search(es)")
    print("dashboard:  uvicorn web.app:app --reload   ->  http://127.0.0.1:8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
