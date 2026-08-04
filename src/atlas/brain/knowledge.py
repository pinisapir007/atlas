from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Finding, SuccessLaw
from atlas.brain.store import BrainStore, JSONFileStore

_EMPTY = {"findings": {}, "success_laws": {}}


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

    Also holds `SuccessLaw`s (added 2026-08-03) — generalized business
    principles extracted from real evidence, the same Intelligence-layer
    concept as a Finding one level more synthesized, so it lives in the
    same store rather than a new, parallel one. `.get("success_laws", {})`
    reads tolerate an older knowledge.json saved before this field existed
    — no migration needed.
    """

    def __init__(self, path: Path = Path(".atlas/knowledge.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"findings": {}, "success_laws": {}}

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

    def save_success_law(self, law: SuccessLaw) -> None:
        data = self._read()
        data.setdefault("success_laws", {})[law.id] = asdict(law)
        self._write(data)

    def success_laws(self) -> list[SuccessLaw]:
        return [SuccessLaw(**law) for law in self._read().get("success_laws", {}).values()]

    def get_success_law(self, law_id: str) -> SuccessLaw:
        raw = self._read().get("success_laws", {}).get(law_id)
        if raw is None:
            raise KeyError(f"no such success law: {law_id}")
        return SuccessLaw(**raw)
