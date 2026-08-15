"""One-off data correction: an errored reading is UNMEASURED, never ABSENT.

⚠️ WHY THIS SCRIPT EXISTS, AND WHY IT IS COMMITTED RATHER THAN RUN QUIETLY.

Commit 925e5b1 fixed `analyze.classify()` so that a live engine which errors or
returns nothing is stored as `unmeasured` — because "we asked and got no answer"
is not evidence of absence. It fixed the code GOING FORWARD and never touched the
rows already in the database.

So run 3 — the run every view defaults to — carried 20 Claude observations that
had failed with HTTP 400 (the Anthropic credit ran out mid-collection) sitting in
the table as `absent`. Consequences, all of them the exact failure this project
argues against:

  · the Track C · Logic tab read "Absent 38 · Dead air 0", when the truth was
    "Absent 18 · Dead air 20";
  · CONTEXT.md celebrated that zero as proof the instrument was healthy;
  · the flagship dataset asserted twenty times that we had looked and were not
    there, on twenty occasions when we never looked at all.

The rates were never wrong — `summarise()` and `benchmark()` both filter on
`error IS NOT NULL` — which is precisely what made this survive: every number on
the page was right while the stored status underneath it was a lie, waiting for
the first consumer that read `status` directly. The Logic tab was that consumer.

The correction is knowable and safe: `error IS NOT NULL` means no answer came
back, and that is `unmeasured` by definition. Nothing is invented, nothing is
deleted, and the error text stays on the row so the reason survives.

    python scripts/fix_errored_status.py --dry-run
    python scripts/fix_errored_status.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeo import db  # noqa: E402

SELECT = """
    SELECT run_id, engine, query_id, status, error
      FROM observations
     WHERE error IS NOT NULL AND error != '' AND status != 'unmeasured'
"""

UPDATE = """
    UPDATE observations
       SET status = 'unmeasured'
     WHERE error IS NOT NULL AND error != '' AND status != 'unmeasured'
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and touch nothing")
    args = ap.parse_args()

    with db.session() as conn:
        rows = [dict(r) for r in conn.execute(SELECT).fetchall()]
        if not rows:
            print("nothing to correct — every errored observation is already unmeasured")
            return 0

        by_run: dict[int, int] = {}
        for r in rows:
            by_run[r["run_id"]] = by_run.get(r["run_id"], 0) + 1

        print(f"{len(rows)} errored observation(s) stored as something other than "
              f"'unmeasured':")
        for run_id, n in sorted(by_run.items()):
            print(f"  run {run_id}: {n}")
        print(f"\n  e.g. run {rows[0]['run_id']} · {rows[0]['engine']} · "
              f"{rows[0]['query_id']} · stored '{rows[0]['status']}'")
        print(f"       error: {str(rows[0]['error'])[:96]}")

        if args.dry_run:
            print("\n--dry-run: nothing written")
            return 0

        conn.execute(UPDATE)
        conn.commit()
        print(f"\ncorrected {len(rows)} row(s) to 'unmeasured'. "
              "The error text is unchanged, so the reason survives the correction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
