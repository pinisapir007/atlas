"""ResourceIndex (2026-08-05, Resource Discovery Engine V1) — the
durable, queryable record of the current set of approved resources.
This is the "Decision Engine must be able to query this index without
rescanning every time" piece: every query method here reads only
already-persisted data (.atlas/resource_index.json) and never touches a
provider, the filesystem, or any network call. Populated exclusively by
resource_discovery_engine.scan_resources() after a real scan — nothing
in this class ever discovers a resource itself, it only stores and
serves what was already discovered.

A full-replacement store, not an incremental merge: each real scan's
complete resource list overwrites the previous index entirely, so a
deleted file's stale entry can never linger — the same "recompute
fresh, nothing is permanently true" discipline decide()/has_materially_
changed() already apply at the Decision Engine level, applied here to a
different kind of state.

Reuses BrainStore/JSONFileStore, the same durable-storage pattern every
other registry in this codebase already uses (KnowledgeBase, Ledger,
BrandRegistry, ...).
"""

from dataclasses import asdict
from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore
from atlas.integrations.base import Resource


class ResourceIndex:
    """Read-mostly, queryable store of the current, real resource
    index — no scanning logic lives here; that's
    resource_discovery_engine.py's job. This class is purely: replace
    the index with a fresh, complete scan result, and answer real
    queries against whatever was last stored."""

    def __init__(self, path: Path = Path(".atlas/resource_index.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"resources": {}}

    def replace_index(self, resources: list[Resource]) -> None:
        """Overwrites the entire index with `resources` — a full
        snapshot of the just-completed real scan, never an incremental
        merge, so a resource that no longer exists is correctly absent
        from the next query rather than lingering as stale data."""
        self._store.write({"resources": {r.path: asdict(r) for r in resources}})

    def all_resources(self) -> list[Resource]:
        """Every resource currently in the index — no scan triggered,
        purely a read of already-discovered, already-persisted data."""
        return [Resource(**raw) for raw in self._read()["resources"].values()]

    def get_resource(self, path: str) -> Resource | None:
        raw = self._read()["resources"].get(path)
        return Resource(**raw) if raw is not None else None

    def resources_in_folder(self, folder_path: str) -> list[Resource]:
        """Every indexed resource whose real path is the given folder or
        a real descendant of it — resolved before comparison, the same
        exact-boundary discipline ResourceAllowlist.is_approved() already
        uses, so a sibling folder with a similar name is never wrongly
        included."""
        resolved_folder = str(Path(folder_path).resolve())
        return [
            r
            for r in self.all_resources()
            if r.path == resolved_folder or r.path.startswith(resolved_folder + "/") or r.path.startswith(resolved_folder + "\\")
        ]

    def find_by_type(self, resource_type: str) -> list[Resource]:
        return [r for r in self.all_resources() if r.resource_type == resource_type]

    def count(self) -> int:
        return len(self._read()["resources"])
