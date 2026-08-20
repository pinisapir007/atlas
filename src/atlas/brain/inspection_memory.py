"""InspectionMemoryStore (2026-08-17, Cognitive State Wiring) -- durable,
cross-process memory for PageCompletionTracker (src/atlas/integrations/
traversal_completion.py), which is itself deliberately in-memory-only and
dependency-free (it must never import atlas.brain, the same layering rule
every other atlas.integrations module already follows -- "atlas.core never
depends on atlas.brain", extended here to atlas.integrations too).

Real, live-audited finding this closes: three separate live-validation
runs against the same real Digistore24 Marketplace page each created a
fresh, empty PageCompletionTracker -- "what's already been inspected" was
silently forgotten every time a new process/script started. Observation
was persisted (MarketplaceCatalogStore); inspection PROGRESS was not.

Reuses the exact BrainStore/JSONFileStore atomic-write pattern every
other durable store in this codebase already uses (KnowledgeBase,
DecisionLog, MarketplaceCatalogStore, OpportunityStore, ...) -- no new
storage architecture. Keyed by a caller-supplied `page_key` (e.g. a real
page URL) since a real, multi-page Marketplace has one real, independent
inspection state per page, never one global tracker conflating them.

`load_tracker()` for a `page_key` never seen before returns a real, valid,
empty PageCompletionTracker -- not an error, not None -- so a caller can
always do `tracker = memory.load_tracker(page_key)` unconditionally,
whether or not this page has ever been tracked before. Observation
(a record being seen again) never resets inspection state -- that
invariant already lives inside PageCompletionTracker.observe() itself
(preserve-on-refresh), unchanged by this module; this module only adds
where that state lives between processes.
"""

from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore
from atlas.integrations.traversal_completion import PageCompletionTracker


class InspectionMemoryStore:
    def __init__(self, path: Path = Path(".atlas/inspection_memory.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"pages": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_tracker(self, page_key: str, tracker: PageCompletionTracker) -> None:
        data = self._read()
        data.setdefault("pages", {})[page_key] = tracker.to_dict()
        self._write(data)

    def load_tracker(self, page_key: str) -> PageCompletionTracker:
        raw = self._read().get("pages", {}).get(page_key)
        if raw is None:
            return PageCompletionTracker()
        return PageCompletionTracker.from_dict(raw)

    def known_page_keys(self) -> list[str]:
        return list(self._read().get("pages", {}).keys())
