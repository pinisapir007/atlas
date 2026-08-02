from typing import Protocol

from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal
from atlas.brain.scoring import score_cash_flow, score_strategic_value
from atlas.brain.valuation import ALL_CRITERIA, blended

MIN_STAGNATION_SAMPLE = 3


class Strategist(Protocol):
    def reallocate(self, goals: list[Goal], kpis: KPIRegistry, log: list[dict]) -> list[dict]: ...


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
    function of (goals, kpis), identical inputs across two calls compute the
    same rank, which already matches what was applied last time, so nothing
    new is emitted. This is what prevents thrash without needing to inspect
    past decisions at all.
    """

    def reallocate(self, goals: list[Goal], kpis: KPIRegistry, log: list[dict]) -> list[dict]:
        active = [g for g in goals if g.status == "active"]
        scored = [g for g in active if _has_any_input(g, kpis)]

        decisions: list[dict] = []
        for horizon, score_fn, other_fn in (
            ("short", score_cash_flow, score_strategic_value),
            ("long", score_strategic_value, score_cash_flow),
        ):
            bucket = [g for g in scored if g.horizon == horizon]
            if not bucket:
                continue
            ranked = sorted(bucket, key=lambda g: score_fn(g, active, kpis), reverse=True)
            bucket_size = len(ranked)
            for rank, goal in enumerate(ranked, start=1):
                decision = self._decide(
                    goal,
                    rank,
                    bucket_size,
                    horizon,
                    cash_flow_score=score_fn(goal, active, kpis) if horizon == "short" else other_fn(goal, active, kpis),
                    strategic_value_score=other_fn(goal, active, kpis) if horizon == "short" else score_fn(goal, active, kpis),
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
            "reason": reason,
        }


def _has_any_input(goal: Goal, kpis: KPIRegistry) -> bool:
    return any(blended(goal, kpis, criterion) is not None for criterion in ALL_CRITERIA)


def _revenue_stagnant_or_declining(goal: Goal, kpis: KPIRegistry) -> bool:
    history = kpis.history(f"revenue_{goal.id}")
    if len(history) < MIN_STAGNATION_SAMPLE:
        return False
    return history[-1]["value"] <= history[-MIN_STAGNATION_SAMPLE]["value"]
