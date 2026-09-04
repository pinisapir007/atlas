"""ResourceAllowlist (2026-08-04, Resource Discovery Engine V1) — the
one durable, explicit record of every folder the founder has actually
approved for scanning. This is the sole source of truth
resource_discovery_engine.py consults before constructing a
LocalFolderProvider — a path not in this registry is never scanned, no
matter what any caller asks for.

Paths are stored resolved (absolute, symlink-free canonical form) so a
relative path or a differently-cased/spelled equivalent can't silently
slip past an intended approval boundary — the same normalize-before-
compare discipline every other exact-match check in this codebase
already uses (e.g. affiliate link validation's parsed, not substring,
`aff=` check).
"""

from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore, update_store


class ResourceAllowlist:
    """Durable record of founder-approved folders — pure CRUD, the same
    shape as BrandRegistry/InfluencerRegistry/KnowledgeBase. No scanning
    logic lives here; this is purely the approval record."""

    def __init__(self, path: Path = Path(".atlas/resource_allowlist.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"folders": []}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def approve_folder(self, path: str) -> None:
        """Records real, explicit founder approval for one folder.
        Idempotent — approving an already-approved folder is a no-op,
        never a duplicate entry."""
        resolved = str(Path(path).resolve())
        def mutate(data):
            if resolved not in data["folders"]:
                data["folders"].append(resolved)

        update_store(self._store, self._read(), mutate)

    def revoke_folder(self, path: str) -> None:
        """Removes a folder's approval — the engine will refuse to scan
        it again from the next scan onward. A no-op if it was never
        approved."""
        resolved = str(Path(path).resolve())
        def mutate(data):
            if resolved in data["folders"]:
                data["folders"].remove(resolved)

        update_store(self._store, self._read(), mutate)

    def approved_folders(self) -> list[str]:
        return list(self._read()["folders"])

    def is_approved(self, path: str) -> bool:
        """True only if `path` is exactly an approved folder, or a real
        descendant of one — resolved before comparison, so this can't be
        fooled by a relative path or a trailing-slash mismatch."""
        resolved = str(Path(path).resolve())
        for folder in self.approved_folders():
            if resolved == folder or resolved.startswith(folder + "/") or resolved.startswith(folder + "\\"):
                return True
        return False
