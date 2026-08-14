"""Seed clearly-marked synthetic history so the trend view is demonstrable.

You cannot know what an assistant answered three weeks ago — no API returns it.
So a smooth multi-week curve on day one is invented, and inventing a baseline is
exactly the error this tool exists to catch in other people's dashboards.

The compromise the brief explicitly allows: use realistic mock data and state the
assumption. Here the assumption is stated in the DATA (`runs.is_synthetic = 1`),
not only in the caption, so no chart can render it as measured history by
accident.

    python scripts/seed_synthetic.py --weeks 3
    python scripts/seed_synthetic.py --clear
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeo import config, db  # noqa: E402
from aeo.engines import ENGINES  # noqa: E402

STATUSES = ["absent", "absent", "absent", "mentioned", "cited"]


def clear() -> int:
    with db.session() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM runs WHERE is_synthetic = 1").fetchone()["c"]
        conn.execute("DELETE FROM runs WHERE is_synthetic = 1")
    return n


def seed(weeks: int, seed_value: int = 7) -> int:
    cfg = config.load()
    rng = random.Random(seed_value)
    engines = [e for e in ENGINES if cfg.engine_enabled(e) and cfg.engine_live(e)]
    now = datetime.now(timezone.utc)
    made = 0

    with db.session() as conn:
        for w in range(weeks, 0, -1):
            at = (now - timedelta(days=w * 7)).isoformat(timespec="seconds")
            run_id = db.start_run(
                conn,
                label="synthetic",
                is_synthetic=True,
                query_set_hash=cfg.query_set_hash,
                engines=",".join(engines),
                started_at=at,
            )
            # A mild upward drift so the line has a shape to read, bounded so it
            # never implies a result the real runs have not earned.
            lift = (weeks - w) * 0.04

            for q in cfg.queries:
                for e in engines:
                    pool = STATUSES + (["mentioned"] if rng.random() < lift else [])
                    status = rng.choice(pool)
                    db.record_observation(conn, run_id, {
                        "query_id": q.id, "query_text": q.text, "intent": q.intent,
                        "engine": e, "is_live": 1, "repeat_n": 1, "status": status,
                        "brand_rank": rng.randint(1, 6) if status != "absent" else None,
                        "answer_chars": rng.randint(700, 2200),
                        "answer_excerpt": "[synthetic backfill — not a measured answer]",
                    })
                    if status == "cited":
                        db.record_citations(conn, run_id, [{
                            "query_id": q.id, "engine": e, "repeat_n": 1,
                            "domain": cfg.owned_domains[0], "url": "", "is_owned": 1,
                        }])
                    for name in rng.sample(cfg.competitor_seeds, k=min(3, len(cfg.competitor_seeds))):
                        db.record_citations(conn, run_id, [{
                            "query_id": q.id, "engine": e, "repeat_n": 1,
                            "domain": name.lower().replace(" ", "") + ".com",
                            "url": "", "is_owned": 0,
                        }])
                        db.record_competitors(conn, run_id, [{
                            "query_id": q.id, "engine": e, "repeat_n": 1,
                            "name": name, "rank": None, "discovered": 0,
                        }])
            db.finish_run(conn, run_id, notes="synthetic backfill")
            made += 1
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=3)
    ap.add_argument("--clear", action="store_true", help="remove all synthetic runs")
    a = ap.parse_args()

    if a.clear:
        print(f"removed {clear()} synthetic run(s)")
        return 0
    print(f"seeded {seed(a.weeks)} synthetic run(s), all flagged is_synthetic=1")
    print("they render as shaded columns and are labelled in the chart itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
