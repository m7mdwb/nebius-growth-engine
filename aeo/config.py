"""Load the measurement contract.

Everything that decides WHAT gets measured lives in config/queries.yaml. This
module only reads it and hashes it, so a run can record which contract it ran
under. Two runs with different hashes are not comparable, and the UI says so
rather than drawing a line between them.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "queries.yaml"
DB_PATH = ROOT / "data" / "aeo.db"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Query:
    id: str
    text: str
    intent: str
    # In the headline "N of 10" benchmark? Branded controls are asked and reported
    # but excluded — see the note at the top of config/queries.yaml.
    benchmark: bool = True


@dataclass
class Config:
    raw: dict
    queries: list[Query] = field(default_factory=list)

    # ---- brand -------------------------------------------------------------
    @property
    def brand_name(self) -> str:
        return self.raw["brand"]["name"]

    @property
    def brand_aliases(self) -> list[str]:
        return list(self.raw["brand"].get("aliases", []))

    @property
    def products(self) -> list[dict]:
        return list(self.raw["brand"].get("products", []))

    @property
    def ambiguous(self) -> list[dict]:
        return list(self.raw["brand"].get("ambiguous", []))

    @property
    def related(self) -> list[str]:
        return list(self.raw["brand"].get("related", []))

    @property
    def owned_domains(self) -> list[str]:
        return list(self.raw.get("domains", {}).get("owned", []))

    @property
    def competitor_seeds(self) -> list[str]:
        return list(self.raw.get("competitor_seeds", []))

    # ---- run ---------------------------------------------------------------
    @property
    def engines(self) -> dict:
        return self.raw.get("engines", {})

    def engine_enabled(self, name: str) -> bool:
        return bool(self.engines.get(name, {}).get("enabled"))

    def engine_live(self, name: str) -> bool:
        return bool(self.engines.get(name, {}).get("live"))

    @property
    def repeats(self) -> int:
        return int(self.raw.get("run", {}).get("repeats", 1))

    @property
    def repeat_subset(self) -> int | None:
        v = self.raw.get("run", {}).get("repeat_subset")
        return int(v) if v is not None else None

    def repeats_for(self, query: Query) -> int:
        """How many times to sample this query.

        Repeating everything triples the cost for no extra insight — the point of
        repeats is to SHOW that a single sample is noisy, which a subset proves
        just as well as the whole set.
        """
        if self.repeats <= 1:
            return 1
        if self.repeat_subset is None:
            return self.repeats
        idx = [q.id for q in self.queries].index(query.id)
        return self.repeats if idx < self.repeat_subset else 1

    # ---- comparability -----------------------------------------------------
    @property
    def query_set_hash(self) -> str:
        """Fingerprint of the measurement contract.

        Covers the queries and the brand/competitor definitions — everything that
        would silently change what a number means. Runs with different hashes get
        a break in the trend line instead of a smooth curve.
        """
        payload = {
            "queries": [(q.id, q.text) for q in self.queries],
            "brand": self.raw["brand"],
            "competitor_seeds": self.competitor_seeds,
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def load(path: Path | None = None) -> Config:
    path = path or CONFIG_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = Config(raw=raw)
    cfg.queries = [
        Query(id=q["id"], text=q["text"], intent=q.get("intent", "unclassified"),
              benchmark=bool(q.get("benchmark", True)))
        for q in raw.get("queries", [])
    ]
    return cfg


def env(name: str) -> str | None:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else None
