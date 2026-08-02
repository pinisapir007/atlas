import json
from dataclasses import asdict
from pathlib import Path

from atlas.assets.publishing_gateway.models import PublishPackage

# Self-contained, file-backed persistence — same pattern as every other
# asset store in this codebase (WorkforceStore, AffiliateStore).
_DEFAULT_PATH = Path(".atlas/publishing_gateway.json")
_EMPTY = {"packages": {}}


class PublishingQueueStore:
    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)

    def _read(self) -> dict:
        if not self._path.exists():
            return json.loads(json.dumps(_EMPTY))
        return json.loads(self._path.read_text())

    def _write(self, data: dict) -> None:
        # Atomic write: serialize to a sibling .tmp file, then rename over
        # the target, so a crash or a concurrent writer mid-write can never
        # leave this store's file half-written/corrupted.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_name(self._path.name + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.replace(self._path)

    def save_package(self, package: PublishPackage) -> None:
        data = self._read()
        data["packages"][package.id] = asdict(package)
        self._write(data)

    def packages(self) -> list[PublishPackage]:
        return [PublishPackage(**p) for p in self._read()["packages"].values()]

    def get_package(self, package_id: str) -> PublishPackage:
        raw = self._read()["packages"].get(package_id)
        if raw is None:
            raise KeyError(f"no such publish package: {package_id}")
        return PublishPackage(**raw)

    def delete_package(self, package_id: str) -> None:
        data = self._read()
        data["packages"].pop(package_id, None)
        self._write(data)
