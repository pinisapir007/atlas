import json
from pathlib import Path
from typing import Protocol


def read_json(path: Path, default: dict) -> dict:
    """Read a JSON document from `path`, or return `default` if it doesn't
    exist yet. Shared by every JSON-file-backed store in atlas.core/brain so
    the read side of the pattern is defined once."""
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json_atomic(path: Path, data: dict) -> None:
    """Write a JSON document to `path` atomically: serialize to a sibling
    `.tmp` file, then rename it over the target. `Path.replace` is atomic on
    both POSIX and Windows (same filesystem), so a crash or a second writer
    mid-write can never leave `path` holding a half-written, corrupted
    document — the previous version stays intact until the new one is
    complete."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.replace(path)


class Store(Protocol):
    def get(self, asset_id: str) -> dict: ...
    def set(self, asset_id: str, state: dict) -> None: ...


class JSONStore:
    """Default Store backend: one JSON file holding {asset_id: state}."""

    def __init__(self, path: Path = Path(".atlas/state.json")):
        self._path = Path(path)

    def get(self, asset_id: str) -> dict:
        return self._read().get(asset_id, {})

    def set(self, asset_id: str, state: dict) -> None:
        data = self._read()
        data[asset_id] = state
        write_json_atomic(self._path, data)

    def _read(self) -> dict:
        return read_json(self._path, {})
