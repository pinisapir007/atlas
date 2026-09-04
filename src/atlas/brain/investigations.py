"""InvestigationStore (2026-08-17, ONE BRAIN Root Implementation) --
durable record of every real, pre-Opportunity Investigation. Reuses
BrainStore/JSONFileStore, the same swappable-backend abstraction every
other real store in this codebase already uses (mirrors
atlas.brain.opportunities.OpportunityStore exactly).
"""

from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Investigation
from atlas.brain.store import BrainStore, JSONFileStore, update_store


class InvestigationStore:
    def __init__(self, path: Path = Path(".atlas/investigations.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"investigations": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_investigation(self, investigation: Investigation) -> None:
        def mutate(data):
            data["investigations"][investigation.id] = asdict(investigation)

        update_store(self._store, self._read(), mutate)

    def investigations(self) -> list[Investigation]:
        return [Investigation(**i) for i in self._read()["investigations"].values()]

    def get_investigation(self, investigation_id: str) -> Investigation:
        raw = self._read()["investigations"].get(investigation_id)
        if raw is None:
            raise KeyError(f"no such investigation: {investigation_id}")
        return Investigation(**raw)

    def by_status(self, status: str) -> list[Investigation]:
        return [i for i in self.investigations() if i.status == status]

    def by_subject(self, category: str, subject_id: str) -> Investigation | None:
        for investigation in self.investigations():
            if investigation.category == category and investigation.subject_id == subject_id:
                return investigation
        return None
