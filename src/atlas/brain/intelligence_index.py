"""IntelligenceIndex (2026-08-05, ATLAS Intelligence Engine V1) — the
one central, durable, queryable record of the current set of collected
intelligence. This is the "single intelligence source for Opportunity
Discovery and future engines" requirement's real storage mechanism:
every query method here reads only already-persisted data
(.atlas/intelligence_index.json) and never triggers a provider or any
real collection call. Populated exclusively by
atlas.brain.intelligence_engine.collect_intelligence() after a real
collection run — nothing in this class collects anything itself.

Deliberately NOT wired into opportunity_ranking.py or
opportunity_discovery_engine.py in this V1 — "do NOT generate
opportunities" is explicit, and wiring this index into Finding/
Opportunity creation would be exactly that. This class exists so a
FUTURE, separate, explicit change can read from it; that wiring is not
made here.

A full-replacement store, not an incremental merge, the same discipline
ResourceIndex already established: each real collection's complete
result overwrites the previous index entirely, so intelligence a
provider no longer reports never lingers as stale data.

Keyed by (provider, subject) rather than a synthetic id — Intelligence
has no single natural unique field the way Resource has `path`, and
generating one would need atlas.brain.models.new_id(), which would pull
atlas.integrations.base into a dependency on atlas.brain (the reversed
direction this codebase's layering forbids). (provider, subject) is a
real, already-present composite identity instead.
"""

from dataclasses import asdict
from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore
from atlas.integrations.base import Intelligence


def _key(provider: str, subject: str) -> str:
    return f"{provider}::{subject}"


class IntelligenceIndex:
    """Read-mostly, queryable store of the current, real intelligence
    index — no collection logic lives here; that's
    intelligence_engine.py's job. Reuses BrainStore/JSONFileStore, the
    same durable-storage pattern every other registry in this codebase
    already uses."""

    def __init__(self, path: Path = Path(".atlas/intelligence_index.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"items": {}}

    def replace_index(self, items: list[Intelligence]) -> None:
        """Overwrites the entire index with `items` — a full snapshot of
        the just-completed real collection, never an incremental merge."""
        self._store.write({"items": {_key(i.provider, i.subject): asdict(i) for i in items}})

    def all_intelligence(self) -> list[Intelligence]:
        """Every item currently in the index — no collection triggered,
        purely a read of already-collected, already-persisted data."""
        return [Intelligence(**raw) for raw in self._read()["items"].values()]

    def by_domain(self, domain: str) -> list[Intelligence]:
        return [i for i in self.all_intelligence() if i.domain == domain]

    def by_subject(self, subject: str) -> list[Intelligence]:
        return [i for i in self.all_intelligence() if i.subject == subject]

    def get(self, provider: str, subject: str) -> Intelligence | None:
        raw = self._read()["items"].get(_key(provider, subject))
        return Intelligence(**raw) if raw is not None else None

    def count(self) -> int:
        return len(self._read()["items"])
