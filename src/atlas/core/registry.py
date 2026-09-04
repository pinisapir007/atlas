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

    def __init__(
        self,
        records: list[AssetRecord] | None = None,
        store: Store | None = None,
        instances: dict[str, object] | None = None,
    ):
        loaded = records if records is not None else discover_manifests()
        self._records = {r.id: r for r in loaded}
        # Pre-seeded instances (2026-08-11, Qualification Run #1 root-cause
        # fix) -- the ONLY real way a caller can hand an asset real,
        # explicit dependencies (e.g. a specific KnowledgeBase) instead of
        # the zero-argument construction _instance() falls back to below.
        # A pre-seeded id is never re-instantiated. Empty/omitted changes
        # nothing for any existing caller.
        self._instances: dict[str, object] = dict(instances) if instances else {}
        self._store = store if store is not None else JSONStore()

    def records(self) -> list[AssetRecord]:
        return sorted(self._records.values(), key=lambda r: r.id)

    def get_record(self, asset_id: str) -> AssetRecord:
        if asset_id not in self._records:
            raise KeyError(f"no such asset: {asset_id}")
        return self._records[asset_id]

    @staticmethod
    def _task_result_key(task_id: str) -> str:
        """Private Store key for one exact Task execution result.

        Kept separate from the asset's aggregate state: Reportable.report()
        remains an asset-level contract, while this record answers the
        different question "what did run() return for this exact Task?".
        """
        return f"__task_result__:{task_id}"

    def task_result(self, task_id: str, asset_id: str | None = None) -> dict | None:
        """Return the durable exact run result metadata for one Task.

        None means no exact result was persisted. `asset_id`, when supplied,
        prevents a stale/mismatched record from being attributed to a Task's
        currently assigned asset.
        """
        state = self._store.get(self._task_result_key(task_id))
        if not isinstance(state, dict) or not state:
            return None
        if asset_id is not None and state.get("asset_id") != asset_id:
            return None
        return state

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
        at = datetime.now(timezone.utc).isoformat()

        self._store.set(
            asset_id,
            {
                "last_verb": verb,
                "result": result if isinstance(result, (str, int, float, bool, type(None))) else str(result),
                "at": at,
            },
        )

        task = kwargs.get("task") if verb == "run" else None
        task_id = getattr(task, "id", None)
        status = result.get("status") if isinstance(result, dict) else None

        if isinstance(task_id, str) and task_id and isinstance(status, str):
            self._store.set(
                self._task_result_key(task_id),
                {
                    "asset_id": asset_id,
                    "status": status,
                    "result": str(result),
                    "at": at,
                },
            )

        return result
