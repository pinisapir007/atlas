from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import LedgerEntry
from atlas.brain.store import BrainStore, JSONFileStore


class Ledger:
    """Durable, append-only record of every real financial event ATLAS has
    recorded — the detail/audit layer beneath KPIRegistry's revenue_<id>/
    cost_<id>/settled_<id> aggregates. Never mutated: a correction is a new
    entry, never an edit to a past one, the same discipline DecisionLog
    already applies to Decisions.

    Reuses BrainStore/JSONFileStore, the same swappable-backend abstraction
    BrainMemory/KnowledgeBase/DecisionLog already use.
    """

    def __init__(self, path: Path = Path(".atlas/ledger.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"entries": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def record(self, entry: LedgerEntry) -> None:
        data = self._read()
        data["entries"][entry.id] = asdict(entry)
        self._write(data)

    def entries(self) -> list[LedgerEntry]:
        return [LedgerEntry(**e) for e in self._read()["entries"].values()]

    def entries_for_goal(self, goal_id: str) -> list[LedgerEntry]:
        return [e for e in self.entries() if e.goal_id == goal_id]

    def entries_for_transaction(self, transaction_id: str) -> list[LedgerEntry]:
        return [e for e in self.entries() if e.transaction_id == transaction_id]
