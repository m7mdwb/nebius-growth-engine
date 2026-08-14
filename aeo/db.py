"""SQLite store.

One file, no server, ships with the repo. The schema is the answer to "what's
the metric and what's the baseline" — every question about what improved is a
query against these four tables.

Two columns carry more weight than they look:

  runs.is_synthetic   marks seeded backfill IN THE DATA, not just in the UI, so
                      a chart cannot accidentally present invented history as
                      measured history.
  runs.query_set_hash fingerprints the measurement contract. Two runs with
                      different hashes are not comparable and the trend line
                      breaks rather than pretending otherwise.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    label           TEXT    NOT NULL DEFAULT 'manual',
    is_synthetic    INTEGER NOT NULL DEFAULT 0,
    query_set_hash  TEXT,
    engines         TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    query_id        TEXT    NOT NULL,
    query_text      TEXT    NOT NULL,
    intent          TEXT,
    engine          TEXT    NOT NULL,
    is_live         INTEGER NOT NULL DEFAULT 1,
    repeat_n        INTEGER NOT NULL DEFAULT 1,
    status          TEXT    NOT NULL,          -- cited | mentioned | absent
    brand_rank      INTEGER,                   -- order of first appearance among named brands
    answer_chars    INTEGER,
    answer_excerpt  TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS citations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    query_id        TEXT    NOT NULL,
    engine          TEXT    NOT NULL,
    repeat_n        INTEGER NOT NULL DEFAULT 1,
    domain          TEXT    NOT NULL,
    url             TEXT,
    is_owned        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS competitors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    query_id        TEXT    NOT NULL,
    engine          TEXT    NOT NULL,
    repeat_n        INTEGER NOT NULL DEFAULT 1,
    name            TEXT    NOT NULL,
    rank            INTEGER,
    discovered      INTEGER NOT NULL DEFAULT 0  -- 1 = not in the seed list
);

CREATE INDEX IF NOT EXISTS ix_obs_run     ON observations(run_id);
CREATE INDEX IF NOT EXISTS ix_obs_query   ON observations(query_id, engine);
CREATE INDEX IF NOT EXISTS ix_cit_run     ON citations(run_id);
CREATE INDEX IF NOT EXISTS ix_cit_domain  ON citations(domain);
CREATE INDEX IF NOT EXISTS ix_comp_run    ON competitors(run_id);
CREATE INDEX IF NOT EXISTS ix_comp_name   ON competitors(name);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def session(path: Path | None = None):
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def start_run(
    conn: sqlite3.Connection,
    *,
    label: str = "manual",
    is_synthetic: bool = False,
    query_set_hash: str | None = None,
    engines: str | None = None,
    started_at: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO runs (started_at, label, is_synthetic, query_set_hash, engines) "
        "VALUES (?,?,?,?,?)",
        (started_at or now(), label, int(is_synthetic), query_set_hash, engines),
    )
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, notes: str | None = None) -> None:
    conn.execute(
        "UPDATE runs SET finished_at = ?, notes = ? WHERE id = ?", (now(), notes, run_id)
    )


def record_observation(conn: sqlite3.Connection, run_id: int, obs: dict) -> None:
    conn.execute(
        "INSERT INTO observations "
        "(run_id, query_id, query_text, intent, engine, is_live, repeat_n, status, "
        " brand_rank, answer_chars, answer_excerpt, error) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            obs["query_id"],
            obs["query_text"],
            obs.get("intent"),
            obs["engine"],
            int(obs.get("is_live", 1)),
            int(obs.get("repeat_n", 1)),
            obs["status"],
            obs.get("brand_rank"),
            obs.get("answer_chars"),
            obs.get("answer_excerpt"),
            obs.get("error"),
        ),
    )


def record_citations(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO citations (run_id, query_id, engine, repeat_n, domain, url, is_owned) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (
                run_id,
                r["query_id"],
                r["engine"],
                int(r.get("repeat_n", 1)),
                r["domain"],
                r.get("url"),
                int(r.get("is_owned", 0)),
            )
            for r in rows
        ],
    )


def record_competitors(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO competitors (run_id, query_id, engine, repeat_n, name, rank, discovered) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (
                run_id,
                r["query_id"],
                r["engine"],
                int(r.get("repeat_n", 1)),
                r["name"],
                r.get("rank"),
                int(r.get("discovered", 0)),
            )
            for r in rows
        ],
    )


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------

def latest_run_id(conn: sqlite3.Connection, real_only: bool = True) -> int | None:
    """Newest finished run, preferring a measured one.

    Falls back to a synthetic run only when no measured run exists, so a fresh
    clone with seeded data still renders. The caller is expected to surface
    `is_synthetic` loudly when that happens — a synthetic run displayed as if it
    were measured is the one failure mode this whole tool argues against.
    """
    base = "SELECT id FROM runs WHERE finished_at IS NOT NULL"
    order = " ORDER BY started_at DESC, id DESC LIMIT 1"
    if real_only:
        row = conn.execute(base + " AND is_synthetic = 0" + order).fetchone()
        if row:
            return int(row["id"])
    row = conn.execute(base + order).fetchone()
    return int(row["id"]) if row else None


def runs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY started_at ASC, id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def observations(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM observations WHERE run_id = ? ORDER BY query_id, engine, repeat_n",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def citations(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM citations WHERE run_id = ?", (run_id,)).fetchall()
    return [dict(r) for r in rows]


def competitors(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM competitors WHERE run_id = ?", (run_id,)).fetchall()
    return [dict(r) for r in rows]
