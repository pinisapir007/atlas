import importlib
from datetime import datetime, timezone

from atlas.core.capabilities import Reportable, Runnable, Triggerable
from atlas.core.loader import discover_manifests
from atlas.core.models import AssetRecord
from atlas.core.store import JSONStore, Store

VERBS: dict[str, tuple[type, str]] = {
    "start": (Runnable, "start"),
    "stop": (Runnable, "stop"),
    "status": (Runnable, "status"),
    "run": (Triggerable, "run"),
    "report": (Reportable, "report"),
}


class UnsupportedVerb(Exception):
    pass


class Registry:
    """Catalog of AssetRecords plus lazy capability dispatch.

    Records are loaded eagerly from manifests (cheap, no imports). An
    asset's entrypoint class is only imported and instantiated the first
    time a capability action is invoked on it.
    """

    def __init__(self, records: list[AssetRecord] | None = None, store: Store | None = None):
        loaded = records if records is not None else discover_manifests()
        self._records = {r.id: r for r in loaded}
        self._instances: dict[str, object] = {}
        self._store = store if store is not None else JSONStore()

    def records(self) -> list[AssetRecord]:
        return sorted(self._records.values(), key=lambda r: r.id)

    def get_record(self, asset_id: str) -> AssetRecord:
        if asset_id not in self._records:
            raise KeyError(f"no such asset: {asset_id}")
        return self._records[asset_id]

    def _instance(self, asset_id: str) -> object:
        if asset_id not in self._instances:
            record = self.get_record(asset_id)
            if not record.entrypoint:
                raise UnsupportedVerb(f"asset '{asset_id}' has no code entrypoint")
            module_name, _, class_name = record.entrypoint.partition(":")
            module = importlib.import_module(module_name)
            self._instances[asset_id] = getattr(module, class_name)()
        return self._instances[asset_id]

    def dispatch(self, asset_id: str, verb: str, **kwargs):
        if verb not in VERBS:
            raise UnsupportedVerb(f"unknown verb: {verb}")
        protocol, method_name = VERBS[verb]
        instance = self._instance(asset_id)
        if not isinstance(instance, protocol):
            kind = self.get_record(asset_id).kind
            raise UnsupportedVerb(f"asset '{asset_id}' ({kind}) does not support '{verb}'")

        result = getattr(instance, method_name)(**kwargs)
        self._store.set(
            asset_id,
            {
                "last_verb": verb,
                "result": result if isinstance(result, (str, int, float, bool, type(None))) else str(result),
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return result
