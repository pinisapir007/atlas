from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Finding
from atlas.brain.store import BrainStore, JSONFileStore

_EMPTY = {"findings": {}}


class KnowledgeBase:
    """Durable record of everything ATLAS's Intelligence layer has
    discovered, independent of whether any given finding ever became a Task
    or a Goal — that lifecycle lives in BrainMemory, a different concern,
    the same separation BrainMemory already draws against
    atlas.core.store.JSONStore.

    Storage is delegated to a BrainStore (default: JSONFileStore, atomic
    writes), reusing the exact abstraction BrainMemory uses rather than
    inventing a second one — a future live data connector's findings land
    here through the same save_finding() call a human-curated or
    AI-researched seed does today.
    """

    def __init__(self, path: Path = Path(".atlas/knowledge.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"findings": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_finding(self, finding: Finding) -> None:
        data = self._read()
        data["findings"][finding.id] = asdict(finding)
        self._write(data)

    def findings(self) -> list[Finding]:
        return [Finding(**f) for f in self._read()["findings"].values()]

    def get_finding(self, finding_id: str) -> Finding:
        raw = self._read()["findings"].get(finding_id)
        if raw is None:
            raise KeyError(f"no such finding: {finding_id}")
        return Finding(**raw)
