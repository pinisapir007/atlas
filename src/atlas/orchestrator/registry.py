from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore, update_store
from atlas.orchestrator.models import ExecutionPlan


class ExecutionPlanRegistry:
    """Durable record of every ExecutionPlan ATLAS has created — pure CRUD,
    the same shape as every other registry in this codebase
    (InfluencerRegistry/CampaignRegistry/KnowledgeBase/DecisionLog/Ledger).
    Domain logic (building a plan, advancing it) lives in
    orchestrator.py, not here.
    """

    def __init__(self, path: Path = Path(".atlas/execution_plans.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"plans": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_plan(self, plan: ExecutionPlan) -> None:
        def mutate(data):
            data["plans"][plan.id] = plan.to_dict()

        update_store(self._store, self._read(), mutate)

    def plans(self) -> list[ExecutionPlan]:
        return [ExecutionPlan.from_dict(p) for p in self._read()["plans"].values()]

    def get_plan(self, plan_id: str) -> ExecutionPlan:
        raw = self._read()["plans"].get(plan_id)
        if raw is None:
            raise KeyError(f"no such execution plan: {plan_id}")
        return ExecutionPlan.from_dict(raw)

    def plans_for_campaign(self, campaign_id: str) -> list[ExecutionPlan]:
        return [p for p in self.plans() if p.campaign_id == campaign_id]
