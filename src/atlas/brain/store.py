from pathlib import Path
from typing import Protocol

from atlas.core.store import read_json, write_json_atomic


class BrainStore(Protocol):
    """Storage backend for BrainMemory's one document (goals, tasks,
    proposals, KPI history, decision log). Mirrors atlas.core.store.Store's
    already-established get/set-a-document shape rather than inventing a new
    one. A future backend (e.g. SQLite) only needs to implement read()/
    write() here — BrainMemory's domain-level API (save_goal, tasks(), ...)
    and every one of its callers stay exactly as they are.
    """

    def read(self) -> dict | None: ...
    def write(self, data: dict) -> None: ...


class JSONFileStore:
    """Default BrainStore backend: one JSON document file, atomic writes."""

    def __init__(self, path: Path = Path(".atlas/brain.json")):
        self._path = Path(path)

    def read(self) -> dict | None:
        return read_json(self._path, None)

    def write(self, data: dict) -> None:
        write_json_atomic(self._path, data)
