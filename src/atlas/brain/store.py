from pathlib import Path
from typing import Protocol

from atlas.core.store import read_json, update_json_atomic, write_json_atomic


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


def update_store(store: BrainStore, default: dict, mutator) -> dict:
    """Perform one read-modify-write transaction when the backend supports it.

    JSONFileStore provides a real thread/process-safe update(). Lightweight
    test or future backends that only implement read()/write() remain
    compatible through the fallback.
    """
    update = getattr(store, "update", None)
    if callable(update):
        return update(default, mutator)

    data = store.read()
    if data is None:
        import json
        data = json.loads(json.dumps(default))

    result = mutator(data)
    if result is not None:
        data = result

    store.write(data)
    return data


class JSONFileStore:
    """Default BrainStore backend: one JSON document file, atomic writes."""

    def __init__(self, path: Path = Path(".atlas/brain.json")):
        self._path = Path(path)

    def read(self) -> dict | None:
        return read_json(self._path, None)

    def write(self, data: dict) -> None:
        write_json_atomic(self._path, data)

    def update(self, default: dict, mutator) -> dict:
        """Perform one atomic read-modify-write transaction."""
        return update_json_atomic(self._path, default, mutator)

    @property
    def path(self) -> Path:
        return self._path
