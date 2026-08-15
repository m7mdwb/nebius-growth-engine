"""Per-run cost caps. The one place in this repo that spends real money.

**A retry loop against a paid actor is real money.** That is the whole reason this
module exists as its own file rather than a couple of counters scattered through the
lead pipeline: if the caps live next to the calls, the day someone adds a third
enrichment step is the day one of them gets forgotten.

Three layers, cheapest failure first:

1. **A call counter per provider.** Hard stop. Hitting it does not truncate silently —
   `BudgetExhausted` propagates, the lead is marked, and the run REPORTS that it ran
   out. A capped run that quietly returns fewer results is indistinguishable from a
   thin day, which is the same seam-versus-absence error the rest of this repo is
   built to avoid.
2. **`max_total_charge_usd` on every Apify call.** The client enforces this server-side,
   so even a runaway actor cannot bill past it. Belt and braces: layer 1 is our count
   of calls, layer 2 is Apify's count of dollars, and they fail independently.
3. **A wall-clock timeout per call**, so a hung actor cannot hold a run open and keep
   accruing compute.

Observed prices, read from the actor definitions on 2026-08-15:
  dev_fusion/linkedin-profile-scraper   $0.01 per profile returned
  harvestapi/linkedin-company           $0.00005 per start, plus a per-company charge
  Serper                                ~$0.001 per query, 2,500 free credits
So the default caps below are roughly **fifteen cents a run**. They exist to stop a
loop, not to ration a demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal


class BudgetExhausted(RuntimeError):
    """The run hit a cap. Raised, never swallowed — the caller must report it."""


class ActorRefused(RuntimeError):
    """The actor ran, succeeded, and returned a refusal INSTEAD OF DATA.

    ⚠️ This is the nastiest failure shape in the whole pipeline, and it cost a run
    to find. harvestapi limits free Apify accounts to 20 runs, and on the 21st it
    does not error — the run SUCCEEDS and the dataset contains one item:

        {"error": "Free users are limited to 20 runs. Please upgrade..."}

    So `items` is non-empty, every field mapping quietly yields None, and the lead
    flows on to be scored as a person with "no job title found" — a *gap*, which
    the scorer is designed to treat as an honest unknown. An account limit had been
    laundered into a fact about the lead.

    A refusal is not a thin record. It is raised, named, and routed to a human.
    """


@dataclass
class Budget:
    """One per run. Not a module-level global, so a web request cannot inherit the
    spend of the request before it."""

    apify_calls: int = 8
    serper_calls: int = 12
    apify_usd_per_call: Decimal = Decimal("0.10")

    spent_apify: int = 0
    spent_serper: int = 0
    log: list[str] = field(default_factory=list)

    def take_apify(self, what: str) -> None:
        if self.spent_apify >= self.apify_calls:
            raise BudgetExhausted(
                f"Apify cap reached ({self.apify_calls} calls) before {what}")
        self.spent_apify += 1
        self.log.append(f"apify {self.spent_apify}/{self.apify_calls}: {what}")

    def take_serper(self, what: str) -> None:
        if self.spent_serper >= self.serper_calls:
            raise BudgetExhausted(
                f"Serper cap reached ({self.serper_calls} queries) before {what}")
        self.spent_serper += 1
        self.log.append(f"serper {self.spent_serper}/{self.serper_calls}: {what}")

    def summary(self) -> dict:
        return {
            "apify": {"used": self.spent_apify, "cap": self.apify_calls},
            "serper": {"used": self.spent_serper, "cap": self.serper_calls},
            "est_usd": round(self.spent_apify * 0.012 + self.spent_serper * 0.001, 4),
        }


def apify_call(actor: str, run_input: dict, budget: Budget, *, what: str,
               timeout_s: int = 240, max_usd: Decimal | None = None) -> list[dict]:
    """One Apify actor run. No retry, by design — see the module docstring.

    ⚠️ Two `apify-client` 3.x breaking changes, both caught by the probe and both of
    which had been sitting dead in this repo since the first commit:
      - it is `run_timeout: timedelta`, NOT `timeout_secs`
      - `call()` returns a `Run` OBJECT, not a dict, so `run["defaultDatasetId"]`
        raises `TypeError: 'Run' object is not subscriptable`
    Neither is subtle once you run it. Neither is visible until you do, which is the
    argument for the probe existing at all — this code was written against the docs,
    read fine, and could never have worked.
    """
    from apify_client import ApifyClient

    budget.take_apify(what)
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(actor).call(
        run_input=run_input,
        run_timeout=timedelta(seconds=timeout_s),
        # Layer 2. Enforced by Apify, not by us.
        #
        # ⚠️ Actors declare their own MINIMUM allowed ceiling and the call is rejected
        # outright below it — `apify~google-search-scraper` refuses anything under
        # $0.50 with "Maximum cost per run is less than the allowed minimum". That is
        # a ceiling, not a charge (a search costs fractions of a cent), but it means
        # one global cap cannot serve every actor. Hence the per-call override.
        max_total_charge_usd=max_usd or budget.apify_usd_per_call,
        logger=None,   # the actor's own container log is noise in a demo terminal
    )
    if not run:
        return []
    # Tolerate both shapes: 2.x handed back a dict, 3.x a Run object. Cheap to
    # support both and it means a client downgrade does not silently break the run.
    dataset_id = getattr(run, "default_dataset_id", None) or (
        run.get("defaultDatasetId") if hasattr(run, "get") else None)
    if not dataset_id:
        return []
    items = list(client.dataset(dataset_id).iterate_items())

    # A one-item dataset whose only content is an error is a refusal wearing the
    # shape of a result. Catch it here, once, for every actor — the alternative is
    # each adapter independently remembering to check, and one of them forgetting.
    if len(items) == 1 and isinstance(items[0], dict):
        only = items[0]
        if set(only) <= {"error", "message", "status", "query", "input"} and (
                only.get("error") or only.get("message")):
            raise ActorRefused(str(only.get("error") or only.get("message"))[:200])
    return items


def serper_search(query: str, budget: Budget, *, what: str, count: int = 5) -> list[dict]:
    """A counted search. Same contract as `search.search` — never raises on a
    provider failure, only on a budget one."""
    from . import search

    budget.take_serper(what)
    return search.search(query, count=count)
