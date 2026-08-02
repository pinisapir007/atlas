import json
from pathlib import Path
from typing import Protocol


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
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())
