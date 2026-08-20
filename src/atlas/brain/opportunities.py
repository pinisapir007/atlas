"""OpportunityStore (2026-08-11, docs/DESIGN_OPPORTUNITY_UNIVERSAL_CORE.md)
-- durable record of every real Opportunity Universal Core, separate from
KnowledgeBase (raw Finding evidence) and DecisionLog (immutable committed
verdicts), the same separation of concerns both already draw. Unlike a
Decision, an Opportunity is a real, evolving State (discovered -> ...
-> selected/lost), so unlike DecisionLog it supports real updates to an
existing record, not only append-once saves.

Reuses BrainStore/JSONFileStore, the same swappable-backend abstraction
every other real store in this codebase already uses.
"""

from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Opportunity
from atlas.brain.store import BrainStore, JSONFileStore


class OpportunityStore:
    def __init__(self, path: Path = Path(".atlas/opportunities.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"opportunities": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_opportunity(self, opportunity: Opportunity) -> None:
        data = self._read()
        data["opportunities"][opportunity.id] = asdict(opportunity)
        self._write(data)

    def opportunities(self) -> list[Opportunity]:
        return [Opportunity(**o) for o in self._read()["opportunities"].values()]

    def get_opportunity(self, opportunity_id: str) -> Opportunity:
        raw = self._read()["opportunities"].get(opportunity_id)
        if raw is None:
            raise KeyError(f"no such opportunity: {opportunity_id}")
        return Opportunity(**raw)

    def by_category(self, category: str) -> list[Opportunity]:
        return [o for o in self.opportunities() if o.category == category]

    def by_stage(self, stage: str) -> list[Opportunity]:
        return [o for o in self.opportunities() if o.stage == stage]
