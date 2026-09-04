from dataclasses import asdict
from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore, update_store
from atlas.hands.models import HandsRequest


class HandsRequestRegistry:
    """Durable record of every real HandsRequest ATLAS has dispatched —
    pure CRUD, the same shape as every other registry in this codebase
    (ExecutionPlanRegistry/CampaignRegistry/InfluencerRegistry). Domain
    logic (executing a request's real steps) lives in
    atlas.hands.dispatch, not here. HandsRequest is a flat dataclass (no
    nested sub-profiles, unlike DigitalInfluencer), so dict(**data)
    round-trips directly — the same precedent Campaign already
    established, no custom to_dict/from_dict needed.
    """

    def __init__(self, path: Path = Path(".atlas/hands_requests.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"requests": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_request(self, request: HandsRequest) -> None:
        def mutate(data):
            data["requests"][request.id] = asdict(request)

        update_store(self._store, self._read(), mutate)

    def requests(self) -> list[HandsRequest]:
        return [HandsRequest(**r) for r in self._read()["requests"].values()]

    def get_request(self, request_id: str) -> HandsRequest:
        raw = self._read()["requests"].get(request_id)
        if raw is None:
            raise KeyError(f"no such hands request: {request_id}")
        return HandsRequest(**raw)

    def requests_for_goal(self, goal_id: str) -> list[HandsRequest]:
        return [r for r in self.requests() if r.goal_id == goal_id]
