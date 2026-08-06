from typing import Protocol

from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal, StrategicObjective
from atlas.brain.scoring import blended_score, score_cash_flow, score_strategic_value
from atlas.brain.valuation import ALL_CRITERIA, blended

MIN_STAGNATION_SAMPLE = 3


class Strategist(Protocol):
    def reallocate(
        self,
        goals: list[Goal],
        kpis: KPIRegistry,
        log: list[dict],
        objective: StrategicObjective | None = None,
    ) -> list[dict]: ...


class SimpleStrategist:
    """Deterministic default capital allocator.

    Ranks active goals within their own horizon bucket by the score
    appropriate to that horizon (cash flow for "short", strategic value for
    "long") and maps rank directly to priority — rank 1 = priority 1 =
    highest. Horizons are never ranked against each other (see
    atlas.brain.scoring), so a long-term asset-building goal never loses
    priority purely for paying slower than a short-term cash goal.

    Pauses a goal only when it is bottom-ranked in its own cohort *and* its
    own measured revenue has shown no improvement over its last 3 readings —
    the same absolute-evidence check atlas.brain.improvement already uses for
    redesign candidates, so a goal is never paused on relative rank alone (a
    goal can be "less amazing than an exceptional peer" while still growing
    fine, and that must not stop it).

    Never mutates a Goal or calls memory/registry — returns decisions for the
    caller (CEOBrain) to apply and log. Emits a decision only when it would
    actually change the goal's priority or status: since scoring is a pure
    function of (goals, kpis, objective), identical inputs across two calls
    compute the same rank, which already matches what was applied last time,
    so nothing new is emitted. This is what prevents thrash without needing
    to inspect past decisions at all.

    `objective` (2026-08-06, Strategic Objective V1): the real ranking key
    is now scoring.blended_score, which reproduces this exact class's
    original fixed rule (short horizon -> cash flow only, long -> strategic
    value only) when `objective` is None -- the honest default before any
    StrategicObjective has ever been set. Passing a real objective is what
    makes the company's current phase actually reweight ranking, not just
    document it.
    """

    def reallocate(
        self,
        goals: list[Goal],
        kpis: KPIRegistry,
        log: list[dict],
        objective: StrategicObjective | None = None,
    ) -> list[dict]:
        active = [g for g in goals if g.status == "active"]
        scored = [g for g in active if _has_any_input(g, kpis)]

        decisions: list[dict] = []
        for horizon in ("short", "long"):
            bucket = [g for g in scored if g.horizon == horizon]
            if not bucket:
                continue
            ranked = sorted(bucket, key=lambda g: blended_score(g, active, kpis, objective), reverse=True)
            bucket_size = len(ranked)
            for rank, goal in enumerate(ranked, start=1):
                decision = self._decide(
                    goal,
                    rank,
                    bucket_size,
                    horizon,
                    cash_flow_score=score_cash_flow(goal, active, kpis),
                    strategic_value_score=score_strategic_value(goal, active, kpis),
                    objective=objective,
                    kpis=kpis,
                )
                if decision is not None:
                    decisions.append(decision)
        return decisions

    def _decide(
        self,
        goal: Goal,
        rank: int,
        bucket_size: int,
        horizon: str,
        cash_flow_score: float,
        strategic_value_score: float,
        objective: StrategicObjective | None,
        kpis: KPIRegistry,
    ) -> dict | None:
        new_priority = rank
        new_status = goal.status

        is_bottom = bucket_size > 1 and rank == bucket_size
        if is_bottom and _revenue_stagnant_or_declining(goal, kpis):
            new_status = "paused"

        if new_priority == goal.priority and new_status == goal.status:
            return None

        reason = f"ranked {rank}/{bucket_size} in {horizon}-horizon cohort"
        reason += f" under objective {objective.id!r} ({objective.description!r})" if objective else " (no strategic objective set — legacy per-horizon rule)"
        if new_status == "paused":
            reason += "; paused — bottom of cohort with no measured revenue improvement over its last 3 readings"

        return {
            "kind": "reallocation",
            "goal_id": goal.id,
            "horizon": horizon,
            "rank": rank,
            "bucket_size": bucket_size,
            "old_priority": goal.priority,
            "new_priority": new_priority,
            "old_status": goal.status,
            "new_status": new_status,
            "cash_flow_score": cash_flow_score,
            "strategic_value_score": strategic_value_score,
            "objective_id": objective.id if objective else None,
            "reason": reason,
        }


def _has_any_input(goal: Goal, kpis: KPIRegistry) -> bool:
    return any(blended(goal, kpis, criterion) is not None for criterion in ALL_CRITERIA)


def _revenue_stagnant_or_declining(goal: Goal, kpis: KPIRegistry) -> bool:
    history = kpis.history(f"revenue_{goal.id}")
    if len(history) < MIN_STAGNATION_SAMPLE:
        return False
    return history[-1]["value"] <= history[-MIN_STAGNATION_SAMPLE]["value"]
