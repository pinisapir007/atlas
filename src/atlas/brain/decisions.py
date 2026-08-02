from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Decision
from atlas.brain.store import BrainStore, JSONFileStore


class DecisionLog:
    """Durable, append-only record of every Decision Engine verdict —
    separate from BrainMemory (goals/tasks/proposals/kpis/log) and from
    KnowledgeBase (raw discovered evidence), the same separation of
    concerns both of those already draw. Decisions are never mutated or
    deleted: a changed verdict for a category is a new Decision with
    superseded_id set, so history is never lost — this is what makes
    "nothing is permanently true" (standing architecture, 2026-08-02)
    inspectable rather than just asserted.

    Reuses BrainStore/JSONFileStore, the same swappable-backend
    abstraction BrainMemory and KnowledgeBase already use.
    """

    def __init__(self, path: Path = Path(".atlas/decisions.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"decisions": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_decision(self, decision: Decision) -> None:
        data = self._read()
        data["decisions"][decision.id] = asdict(decision)
        self._write(data)

    def decisions(self) -> list[Decision]:
        return [Decision(**d) for d in self._read()["decisions"].values()]

    def get_decision(self, decision_id: str) -> Decision:
        raw = self._read()["decisions"].get(decision_id)
        if raw is None:
            raise KeyError(f"no such decision: {decision_id}")
        return Decision(**raw)

    def latest_for_category(self, category: str) -> Decision | None:
        """The most recent Decision for a category, or None if it's never
        been decided on. "Most recent" by created_at, not by id order."""
        matches = [d for d in self.decisions() if d.category == category]
        if not matches:
            return None
        return max(matches, key=lambda d: d.created_at)
