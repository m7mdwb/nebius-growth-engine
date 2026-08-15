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


# ---------------------------------------------------------------------------
# Track A — prior headcount readings, so the growth proxy has something to compare
# ---------------------------------------------------------------------------

# Same problem, same answer. Headcount growth needs two sightings and the first run
# of a fresh clone only ever has one, so the growth path is invisible in a demo — it
# correctly reports "not yet measured" for every company, which is honest and shows
# nothing working.
#
# ⚠️ The seeded reading is marked `source = 'synthetic-backfill'` IN THE ROW, not just
# in a caption, exactly like runs.is_synthetic. `leads.growth()` reads that column and
# labels any growth figure derived from it, so a seeded comparison can never be
# presented as a measured one. Clear them with --clear-snapshots before a real run.
SNAPSHOT_SOURCE = "synthetic-backfill"


def seed_snapshots(days_ago: int = 30, shrink_pct: float = 6.0) -> int:
    """Give every company we have already seen one older, smaller reading.

    Deliberately derived from the CURRENT real headcount rather than invented from
    nothing: the growth percentage is then the only fabricated quantity, and it is a
    stated assumption rather than a fictional company.
    """
    from datetime import datetime, timedelta, timezone

    at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
    made = 0
    with db.session() as conn:
        rows = conn.execute(
            "SELECT domain, company_name, MAX(headcount) hc FROM company_snapshots "
            "WHERE source != ? AND headcount IS NOT NULL GROUP BY domain",
            (SNAPSHOT_SOURCE,)).fetchall()
        for r in rows:
            before = int(round(r["hc"] * (1 - shrink_pct / 100.0)))
            conn.execute(
                "INSERT INTO company_snapshots (domain, observed_at, headcount, "
                "company_name, source) VALUES (?,?,?,?,?)",
                (r["domain"], at, before, r["company_name"], SNAPSHOT_SOURCE))
            made += 1
    return made


def clear_snapshots() -> int:
    with db.session() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM company_snapshots WHERE source = ?",
                         (SNAPSHOT_SOURCE,)).fetchone()["c"]
        conn.execute("DELETE FROM company_snapshots WHERE source = ?", (SNAPSHOT_SOURCE,))
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=3)
    ap.add_argument("--clear", action="store_true", help="remove all synthetic runs")
    ap.add_argument("--snapshots", action="store_true",
                    help="Track A: seed a prior headcount reading per known company, "
                         "marked synthetic, so growth has something to compare against")
    ap.add_argument("--days-ago", type=int, default=30)
    ap.add_argument("--clear-snapshots", action="store_true")
    a = ap.parse_args()

    if a.clear_snapshots:
        print(f"removed {clear_snapshots()} synthetic snapshot(s)")
        return 0
    if a.snapshots:
        n = seed_snapshots(a.days_ago)
        print(f"seeded {n} prior headcount reading(s) dated {a.days_ago} days ago, "
              f"all flagged source='{SNAPSHOT_SOURCE}'")
        print("growth computed against these is labelled as synthetic in the UI")
        return 0
    if a.clear:
        print(f"removed {clear()} synthetic run(s)")
        return 0
    print(f"seeded {seed(a.weeks)} synthetic run(s), all flagged is_synthetic=1")
    print("they render as shaded columns and are labelled in the chart itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
