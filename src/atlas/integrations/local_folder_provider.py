"""LocalFolderProvider (2026-08-04, Resource Discovery Engine V1) — the
first real ResourceProvider: real local filesystem folders, metadata
only.

Safety discipline, stated once here since every other module in this
engine relies on it holding: this provider NEVER scans anything it
wasn't explicitly constructed with. There is no default folder, no
"likely" location, no fallback to cwd or the user's home directory —
only the exact, real paths passed into `__init__`. An empty list means
zero scanning, full stop; `fetch_resources()` returns None rather than
walking anything. This is deliberately enforced here too, not only by
the caller (atlas.brain.resource_allowlist / resource_discovery_engine)
— defense in depth, the same principle RiskPolicy's own fail-closed
design already applies one layer up in this codebase (unproven safety
never defaults to "proceed").

Metadata only, never content: real path, type (file/folder), size,
modified time, and a real SHA-256 hash for files — computing that hash
requires transiently reading a file's real bytes, but nothing beyond
the digest is ever kept or returned. Symlinks are recorded but never
followed, so an approved folder can never be used to silently reach
somewhere outside it via a symlink.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from atlas.integrations.base import Resource

_HASH_CHUNK_SIZE = 65536


def _hash_file(path: Path) -> str | None:
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def _isoformat(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


class LocalFolderProvider:
    """Real, read-only, metadata-only local folder scanning — the exact
    folders given to __init__, recursively, and nothing else. See this
    module's docstring for the full safety discipline this class
    enforces independently of any caller."""

    name = "local_folder"

    def __init__(self, approved_folders: list[str]):
        self._approved_folders = [str(f) for f in approved_folders]

    def fetch_resources(self) -> list[Resource] | None:
        if not self._approved_folders:
            return None  # never scans anything without an explicit approved folder

        results: list[Resource] = []
        for folder in self._approved_folders:
            results.extend(self._scan_folder(folder))
        return results

    def _scan_folder(self, folder: str) -> list[Resource]:
        root = Path(folder)
        if not root.is_dir():
            return [
                Resource(
                    provider=self.name,
                    path=folder,
                    resource_type="folder",
                    error=f"approved path is not a real, accessible directory: {folder}",
                )
            ]

        results: list[Resource] = []
        for entry in root.rglob("*"):
            results.append(self._describe(entry))
        return results

    def _describe(self, entry: Path) -> Resource:
        path_str = str(entry)

        if entry.is_symlink():
            # Never followed -- a symlink inside an approved folder could
            # otherwise point anywhere on disk, silently defeating the
            # allow-list. Recorded, not scanned into.
            return Resource(
                provider=self.name,
                path=path_str,
                resource_type="symlink",
                error="symlink skipped -- not followed, for safety",
            )

        try:
            stat = entry.stat()
        except OSError as exc:
            return Resource(
                provider=self.name,
                path=path_str,
                resource_type="folder" if entry.is_dir() else "file",
                error=str(exc),
            )

        if entry.is_dir():
            return Resource(
                provider=self.name,
                path=path_str,
                resource_type="folder",
                modified_at=_isoformat(stat.st_mtime),
            )

        return Resource(
            provider=self.name,
            path=path_str,
            resource_type="file",
            size_bytes=stat.st_size,
            modified_at=_isoformat(stat.st_mtime),
            content_hash=_hash_file(entry),
        )
