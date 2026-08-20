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

        # Fail-closed (2026-08-15, Delegator Fail-Closed Fix, Foundation
        # Design approved): only assets that actually declare this
        # category are ever tried. The old behavior -- falling through to
        # every OTHER registered asset, in id-sorted order, until one
        # happened not to raise UnsupportedVerb -- was a proven, recurring
        # bug class (the exact failure that once caused a Campaign-review
        # Task to be silently dispatched to an unrelated asset before
        # campaign_execution was registered). "I don't have a registered
        # capability for this" is now an honest, auditable answer -- never
        # a guess.
        for record in matched:
            try:
                result = registry.dispatch(record.id, "run", task=task)
            except UnsupportedVerb:
                continue
            task.assigned_asset_id = record.id
            task.transition("delegated", f"delegated to {record.id}")
            return result if isinstance(result, dict) else None

        task.transition(
            "blocked",
            f"no registered asset declares category={task.category!r} — fail-closed, never dispatched to an unrelated asset",
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
