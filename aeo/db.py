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
    error           TEXT,
    -- The organic SERP domains for the same query, where the surface exposes them
    -- (AI Overviews only). Kept so "does SEO feed AEO" is a query against measured
    -- data rather than an opinion. JSON list of domains.
    serp_domains    TEXT,
    -- What this call actually consumed, off the response rather than estimated.
    -- ⚠️ `web_searches` is here because it is the term an estimate always misses:
    -- search results are injected into the INPUT, so a one-line query can reach
    -- the model as tens of thousands of tokens, and the search line itself can
    -- exceed the token line. See aeo/pricing.py.
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    web_searches    INTEGER,
    cost_usd        REAL
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

-- Track A ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lead_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    fit_hash        TEXT,                       -- fingerprint of the fit definition
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES lead_runs(id) ON DELETE CASCADE,
    email           TEXT    NOT NULL,
    name            TEXT,
    company         TEXT,
    domain          TEXT,
    source          TEXT,
    enriched        INTEGER NOT NULL DEFAULT 0, -- 0 = we could not look it up
    industry        TEXT,
    headcount       INTEGER,
    seniority       TEXT,
    job_function    TEXT,
    title           TEXT,
    score           INTEGER,
    breakdown       TEXT,                       -- JSON: every point and where it came from
    route           TEXT    NOT NULL,
    route_why       TEXT,                       -- the reasoning, stored WITH the decision
    sla_minutes     INTEGER,
    disqualified    TEXT,                       -- reason, or NULL
    message         TEXT,
    evidence        TEXT,                       -- JSON: which facts the draft used
    error           TEXT,
    -- real-enrichment columns ------------------------------------------------
    linkedin_url    TEXT,
    headcount_growth TEXT,                      -- '+12% over 34d', or NULL = unknown
    reconciliation  TEXT,                       -- JSON: verified | weak | mismatch | thin
    unknowns        TEXT,                       -- JSON: enrichment fields we never got
    gaps            TEXT,                       -- JSON: SCORING factors we could not measure
    pain_points     TEXT,                       -- JSON: inferred by the model, from evidence
    trace           TEXT                        -- JSON: what the lookup actually did
);

CREATE INDEX IF NOT EXISTS ix_leads_run   ON leads(run_id);

-- 🔑 The growth proxy, and the reason it is a TABLE and not a column.
--
-- LinkedIn publishes what a company is today and keeps no public history —
-- `peopleStats` looked like it might carry a series and does not; it is a breakdown
-- of where current staff sit. So headcount growth cannot be read from one scrape at
-- any price.
--
-- It can be MEASURED, though, by writing down what we saw and looking again later.
-- One row per company per sighting; growth is computed on the second one. Until a
-- company has two rows its growth is `unknown` and scores ZERO — declared, never a
-- zero that reads as "flat". Exactly the same discipline as runs.is_synthetic on the
-- AEO side: the honest answer to "we cannot know this yet" is to say so in the data.
CREATE TABLE IF NOT EXISTS company_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain          TEXT    NOT NULL,
    observed_at     TEXT    NOT NULL,
    headcount       INTEGER,
    company_name    TEXT,
    source          TEXT    NOT NULL DEFAULT 'linkedin'
);

CREATE INDEX IF NOT EXISTS ix_snap_domain ON company_snapshots(domain, observed_at);

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
    # ⚠️ Both of these were learned by losing a run.
    #
    # A Track C collection is ~25 minutes of network calls that commits after every
    # observation. Looking up one lead in the web app at the same time — which is a
    # completely reasonable thing to do during a walkthrough — made the collector die
    # with "database is locked" at step 12 of 80, throwing away everything after it and
    # the money spent on it.
    #
    # SQLite's default busy timeout is ZERO: a writer that finds the database locked
    # fails instantly rather than waiting the few milliseconds the other commit needs.
    # WAL then lets readers carry on while a write is in flight, so the dashboard stays
    # responsive during a collection instead of blocking on it.
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


# Columns added after the first release. `CREATE TABLE IF NOT EXISTS` does exactly
# nothing to a table that already exists, so a database created by an earlier version
# silently keeps its old shape and then fails on INSERT with "no such column" —
# halfway through a paid run, which is the worst possible moment.
#
# The alternative was "delete data/aeo.db and start again", and that is a bad
# instruction to put in a README: this file holds the company_snapshots that the
# headcount-growth proxy depends on, and those cannot be re-fetched — a snapshot is a
# reading of a moment that has passed. Losing them resets the only history the tool
# accumulates.
_ADDED_COLUMNS = {
    "observations": [("serp_domains", "TEXT"), ("input_tokens", "INTEGER"),
                     ("output_tokens", "INTEGER"), ("web_searches", "INTEGER"),
                     ("cost_usd", "REAL")],
    "leads": [("linkedin_url", "TEXT"), ("headcount_growth", "TEXT"),
              ("reconciliation", "TEXT"), ("unknowns", "TEXT"), ("gaps", "TEXT"),
              ("pain_points", "TEXT"), ("trace", "TEXT"), ("cost_usd", "REAL")],
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in _ADDED_COLUMNS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not have:
            continue        # table not created yet; SCHEMA will make it correctly
        for name, decl in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


@contextmanager
def session(path: Path | None = None):
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
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
    import json as _json
    conn.execute(
        "INSERT INTO observations "
        "(run_id, query_id, query_text, intent, engine, is_live, repeat_n, status, "
        " brand_rank, answer_chars, answer_excerpt, error, serp_domains, "
        " input_tokens, output_tokens, web_searches, cost_usd) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
            _json.dumps(obs.get("serp_domains") or []),
            (obs.get("usage") or {}).get("input_tokens"),
            (obs.get("usage") or {}).get("output_tokens"),
            (obs.get("usage") or {}).get("web_searches"),
            obs.get("cost_usd"),
        ),
    )


def run_cost(conn: sqlite3.Connection, run_id: int) -> dict:
    """What one run cost, as a query rather than an estimate."""
    r = conn.execute(
        "SELECT COUNT(*) calls, COALESCE(SUM(input_tokens),0) inp, "
        " COALESCE(SUM(output_tokens),0) out, COALESCE(SUM(web_searches),0) searches, "
        " COALESCE(SUM(cost_usd),0) usd "
        "FROM observations WHERE run_id = ? AND cost_usd IS NOT NULL", (run_id,)
    ).fetchone()
    d = dict(r)
    d["usd"] = round(d["usd"], 4)
    return d


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


# --------------------------------------------------------------------------
# Track A
# --------------------------------------------------------------------------

def start_lead_run(conn: sqlite3.Connection, *, fit_hash: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO lead_runs (started_at, fit_hash) VALUES (?,?)", (now(), fit_hash)
    )
    return int(cur.lastrowid)


def finish_lead_run(conn: sqlite3.Connection, run_id: int, notes: str | None = None) -> None:
    conn.execute("UPDATE lead_runs SET finished_at = ?, notes = ? WHERE id = ?",
                 (now(), notes, run_id))


def record_lead(conn: sqlite3.Connection, run_id: int, lead: dict) -> int:
    import json as _json
    cur = conn.execute(
        "INSERT INTO leads (run_id, email, name, company, domain, source, enriched, "
        " industry, headcount, seniority, job_function, title, score, breakdown, "
        " route, route_why, sla_minutes, disqualified, message, evidence, error, "
        " linkedin_url, headcount_growth, reconciliation, unknowns, gaps, pain_points, "
        " trace, cost_usd) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id, lead["email"], lead.get("name"), lead.get("company"),
            lead.get("domain"), lead.get("source"), int(lead.get("enriched", 0)),
            lead.get("industry"), lead.get("headcount"), lead.get("seniority"),
            lead.get("job_function"), lead.get("title"), lead.get("score"),
            _json.dumps(lead.get("breakdown") or []), lead["route"],
            lead.get("route_why"), lead.get("sla_minutes"), lead.get("disqualified"),
            lead.get("message"), _json.dumps(lead.get("evidence") or []), lead.get("error"),
            lead.get("linkedin_url"), lead.get("headcount_growth"),
            _json.dumps(lead.get("reconciliation") or {}),
            _json.dumps(lead.get("unknowns") or []),
            _json.dumps(lead.get("gaps") or []),
            _json.dumps(lead.get("pain_points") or []),
            _json.dumps(lead.get("trace") or []),
            lead.get("cost_usd"),
        ),
    )
    return int(cur.lastrowid)


# --- the growth proxy ------------------------------------------------------

def record_snapshot(conn: sqlite3.Connection, *, domain: str, headcount: int | None,
                    company_name: str | None, source: str = "linkedin") -> None:
    conn.execute(
        "INSERT INTO company_snapshots (domain, observed_at, headcount, company_name, source) "
        "VALUES (?,?,?,?,?)", (domain, now(), headcount, company_name, source))


def prior_snapshot(conn: sqlite3.Connection, domain: str,
                   min_age_days: int = 7) -> dict | None:
    """The most recent snapshot at least `min_age_days` old.

    ⚠️ The age floor is the point. Two readings taken an hour apart differ by scraper
    noise and rounding, not by hiring, and dividing by a tiny elapsed time turns that
    noise into a huge annualised "growth rate". Same argument as the AEO side's noise
    band: movement smaller than the measurement spread is not a result.
    """
    row = conn.execute(
        "SELECT * FROM company_snapshots WHERE domain = ? AND headcount IS NOT NULL "
        "AND observed_at <= datetime('now', ?) ORDER BY observed_at DESC LIMIT 1",
        (domain, f"-{int(min_age_days)} days"),
    ).fetchone()
    return dict(row) if row else None


def latest_lead_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM lead_runs WHERE finished_at IS NOT NULL "
        "ORDER BY started_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return int(row["id"]) if row else None


def lead_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM lead_runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def leads(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    import json as _json
    rows = conn.execute("SELECT * FROM leads WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for col, empty in (("breakdown", "[]"), ("evidence", "[]"), ("unknowns", "[]"),
                           ("gaps", "[]"), ("pain_points", "[]"), ("trace", "[]"),
                           ("reconciliation", "{}")):
            try:
                d[col] = _json.loads(d.get(col) or empty)
            except (TypeError, ValueError):
                d[col] = _json.loads(empty)
        out.append(d)
    return out
