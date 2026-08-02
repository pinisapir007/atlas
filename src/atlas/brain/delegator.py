from atlas.brain.models import ALWAYS_REQUIRES_APPROVAL, Proposal, Task
from atlas.brain.risk import REDESIGN_PREFIX
from atlas.core.registry import Registry, UnsupportedVerb


def is_structural(category: str) -> bool:
    """Categories that can never be auto-executed: creating an asset,
    recruiting an agent, or redesigning part of the business. These always
    produce a Proposal for a human, never a Registry dispatch."""
    return category in ALWAYS_REQUIRES_APPROVAL or category.startswith(REDESIGN_PREFIX)


class Delegator:
    """Turns a prioritized Task into either a Registry dispatch (routine
    work delegated to a capable asset) or a Proposal (structural change
    that needs a human decision, per atlas.brain.risk / the "do not create
    assets automatically" boundary)."""

    def __init__(self, memory):
        self._memory = memory

    def delegate(
        self,
        task: Task,
        registry: Registry,
        evidence: list[str] | None = None,
        baseline_metrics: dict | None = None,
    ) -> dict | None:
        """Returns the raw dispatch result on a successful delegation (used by
        atlas.brain.kpi_intake to attribute revenue/cost signals), or None for
        a structural proposal or a blocked task."""
        if is_structural(task.category):
            self._propose(task, evidence or [], baseline_metrics or {})
            return None

        candidates = [r for r in registry.records() if r.entrypoint]
        matched = [r for r in candidates if task.category in r.config.get("categories", [])]
        unmatched = [r for r in candidates if r not in matched]

        for record in matched + unmatched:
            try:
                result = registry.dispatch(record.id, "run", task=task)
            except UnsupportedVerb:
                continue
            task.assigned_asset_id = record.id
            task.transition("delegated", f"delegated to {record.id}")
            return result if isinstance(result, dict) else None

        task.transition(
            "blocked",
            f"no capable asset for required_capability={task.required_capability}",
        )
        return None

    def _propose(self, task: Task, evidence: list[str], baseline_metrics: dict) -> None:
        kind = "redesign" if task.category.startswith(REDESIGN_PREFIX) else task.category
        proposal = Proposal(
            task_id=task.id,
            kind=kind,
            rationale=task.description,
            evidence=evidence,
            baseline_metrics=baseline_metrics,
        )
        self._memory.save_proposal(proposal)
        task.transition("pending_approval", f"structural change proposed: {proposal.id}")
