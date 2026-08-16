"""Build `data/demo.db` — the database this repo ships with.

⚠️ CONSTRAINT 4. `data/aeo.db` holds real people. Track A scrapes live LinkedIn
profiles, so that file contains names, work email addresses, profile URLs, job
histories and first-touch emails addressed to real humans by name. It is gitignored
and it stays gitignored.

But a fresh clone with no database renders an honest, useless "No runs yet" on every
tab, and asking a reviewer to spend $3 of their own API credit before they can see
anything is a bad first five minutes. So the repo ships a REDACTED COPY.

What survives, because it is what makes the method judgeable:
  · every Track C run, observation, citation and competitor — no personal data there
  · every lead's score, the breakdown behind it, the routing and its reasoning
  · the reconciliation verdict, and the company firmographics
  · the COUNT of facts each draft cited, which is the "is this a mail-merge" check

What goes:
  · names, profile URLs, the drafted messages, the enrichment trace
  · the local part of every email — the DOMAIN stays, because it is the
    reconciliation key and it names a company rather than a person
  · the person's name wherever the MODEL wrote it into free text, which is the one
    that got missed the first time: pain points are generated prose and the model
    writes people into them ("as CEO Klein carries the gap between...").

    python scripts/make_demo_db.py
    python scripts/make_demo_db.py --check    # verify the shipped copy is clean
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aeo.config import DB_PATH  # noqa: E402

DEMO_PATH = DB_PATH.parent / "demo.db"

# Fields nulled or masked outright.
_WIPE = ("linkedin_url", "trace")


def _tokens(name: str, email: str) -> list[str]:
    """Name parts to strip out of model-written text, from the name AND the mailbox.

    christian.klein@ is the same name in another shape, so the mailbox is a second
    source of tokens rather than only a field to mask.
    """
    local = (email or "").split("@")[0]
    return [t for t in re.split(r"[\s._-]+", f"{name or ''} {local}") if len(t) >= 3]


def _scrub(text: str, tokens: list[str]) -> str:
    out = text or ""
    for t in tokens:
        out = re.sub(rf"\b{re.escape(t)}\b", "—", out, flags=re.IGNORECASE)
    return out


def build() -> Path:
    if not DB_PATH.exists():
        raise SystemExit(f"no database at {DB_PATH} — nothing to copy")

    shutil.copy2(DB_PATH, DEMO_PATH)
    conn = sqlite3.connect(DEMO_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM leads").fetchall()
    for r in rows:
        d = dict(r)
        toks = _tokens(d.get("name") or "", d.get("email") or "")
        email = d.get("email") or ""
        domain = email.split("@")[-1] if "@" in email else ""
        conn.execute(
            "UPDATE leads SET name = ?, email = ?, linkedin_url = NULL, message = ?, "
            "trace = '[]', pain_points = ?, evidence = ?, route_why = ?, "
            "disqualified = ? WHERE id = ?",
            (
                "— redacted —",
                f"•••@{domain}" if domain else "— redacted —",
                # The count of cited facts survives; the message does not.
                (f"— draft redacted. It cited {len(_json_list(d.get('evidence')))} "
                 f"specific facts from the record; run the app with your own keys to "
                 f"read it.") if d.get("message") else None,
                _scrub(d.get("pain_points") or "[]", toks),
                _scrub(d.get("evidence") or "[]", toks),
                _scrub(d.get("route_why") or "", toks),
                _scrub(d.get("disqualified") or "", toks) or None,
                d["id"],
            ),
        )

    # Snapshots carry a company domain and headcount. No personal data, and the growth
    # proxy is unreadable without them, so they stay.
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    return DEMO_PATH


def _json_list(raw) -> list:
    import json
    try:
        return json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []


def check() -> int:
    """Read the SHIPPED BYTES and look for anything that identifies a person.

    Deliberately reads the file rather than the code that wrote it: the first leak
    got through because the redaction was verified by reading the function.
    """
    if not DEMO_PATH.exists():
        print("no demo.db — run without --check first")
        return 1

    blob = DEMO_PATH.read_bytes().decode("utf-8", errors="ignore")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    real = conn.execute("SELECT name, email FROM leads").fetchall()
    conn.close()

    hits = []
    # 1. Names currently in the live database.
    for r in real:
        for t in _tokens(r["name"] or "", r["email"] or ""):
            if re.search(rf"\b{re.escape(t)}\b", blob, re.IGNORECASE):
                hits.append(t)

    # 2. ⚠️ Shape-based checks, which do NOT depend on the live database. The token
    #    scan above only looks for people who are still in aeo.db — so a rehearsal
    #    lead deleted from the live copy but left in the shipped one would pass
    #    unnoticed. These catch the shape of the thing instead of the specific person.
    if "linkedin.com/in/" in blob:
        hits.append("a linkedin profile URL")
    for m in re.finditer(r"\b[a-z][a-z'-]{1,20}[._][a-z][a-z'-]{1,20}@[a-z0-9.-]+\.[a-z]{2,}",
                         blob, re.IGNORECASE):
        hits.append(f"an unmasked mailbox: {m.group(0)}")
    # A masked address is •••@domain; anything with letters before the @ is not masked.
    for m in re.finditer(r"\"email\"\s*:\s*\"(?!•)[^\"]+\"", blob):
        hits.append(f"an email field that is not masked: {m.group(0)[:48]}")

    if hits:
        print("LEAK — these appear in the shipped file:", sorted(set(hits)))
        return 1
    print(f"clean: no personal tokens in {DEMO_PATH.name} "
          f"({DEMO_PATH.stat().st_size // 1024} KB)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped copy carries no personal data")
    a = ap.parse_args()
    if a.check:
        return check()
    p = build()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
