from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Task

WON_STAGE = "won"


def record_revenue(task: Task, result, kpis: KPIRegistry) -> None:
    """Attributes a just-completed dispatch's revenue/cost signal to the
    task's goal, if the result shape is recognized. Fail-closed: an
    unrecognized or malformed shape (Research's, or anything unknown)
    records nothing rather than guessing at a number."""
    if not isinstance(result, dict):
        return
    if "revenue_generated" in result:
        _record_revenue_channel_result(task, result, kpis)
    elif "opportunities" in result:
        _record_recruitment_result(result, kpis)


def _record_revenue_channel_result(task: Task, result: dict, kpis: KPIRegistry) -> None:
    """Revenue's shape: one incremental amount from this one execution —
    accumulate onto the goal's running total."""
    amount = result.get("revenue_generated")
    if not isinstance(amount, (int, float)):
        return
    name = f"revenue_{task.goal_id}"
    current = kpis.latest(name) or 0.0
    kpis.record(name, current + amount)


def _record_recruitment_result(result: dict, kpis: KPIRegistry) -> None:
    """Recruitment's shape: attribute strictly via each opportunity's own
    stored goal_id (set once at creation — see RecruitmentAgent), never via
    the task that happened to trigger this dispatch. Untagged opportunities
    (goal_id is None) are skipped, not bucketed anywhere. Only "won" stage
    counts as realized revenue — pipeline/proposal-stage figures are a
    projection, not a fact, and recording them as measured data would be
    premature. Cost is derived from real computed data (recurring revenue
    minus the gross-profit margin compute_revenue_model already produces),
    never invented. Both totals are a full recomputation from the current
    opportunity list, written as a replacement reading, not accumulated —
    this is what keeps repeated dispatches idempotent instead of inflating.
    """
    opportunities = result.get("opportunities")
    if not isinstance(opportunities, list):
        return

    totals: dict[str, dict[str, float]] = {}
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or opportunity.get("stage") != WON_STAGE:
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id:
            continue  # untagged — no fallback attribution
        revenue = opportunity.get("recurring_monthly_revenue", 0.0)
        profit = opportunity.get("estimated_gross_profit", 0.0)
        bucket = totals.setdefault(goal_id, {"revenue": 0.0, "cost": 0.0})
        bucket["revenue"] += revenue
        bucket["cost"] += revenue - profit

    for goal_id, goal_totals in totals.items():
        kpis.record(f"revenue_{goal_id}", goal_totals["revenue"])
        kpis.record(f"cost_{goal_id}", goal_totals["cost"])


def record_manual_revenue(goal_id: str, amount: float, cost: float | None, kpis: KPIRegistry) -> None:
    """A direct, founder-entered revenue reading — for real conversions
    reported by an affiliate network's own dashboard, where no Task dispatch
    result exists to shape-dispatch from (unlike record_revenue() above).
    Same accumulate semantics as _record_revenue_channel_result: one-off
    incremental amount per real conversion, added onto the goal's running
    total — never a replacement reading, since each call reports one more
    real event, not a full recomputation."""
    current_revenue = kpis.latest(f"revenue_{goal_id}") or 0.0
    kpis.record(f"revenue_{goal_id}", current_revenue + amount)
    if cost is not None:
        current_cost = kpis.latest(f"cost_{goal_id}") or 0.0
        kpis.record(f"cost_{goal_id}", current_cost + cost)
