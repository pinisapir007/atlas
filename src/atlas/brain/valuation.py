from datetime import datetime

from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal

MATURITY_SAMPLE = 6

# expected_revenue, required_investment, time_to_first_profit have a KPI-derived
# counterpart via the revenue_<goal_id>/cost_<goal_id> convention. scalability,
# automation_potential, and long_term_strategic_value have no measured counterpart
# in the system today and stay founder-judgment inputs indefinitely — see CLAUDE.md.
MEASURABLE_CRITERIA = {"expected_revenue", "required_investment", "time_to_first_profit"}
JUDGMENT_CRITERIA = {"scalability", "automation_potential", "long_term_strategic_value"}
ALL_CRITERIA = MEASURABLE_CRITERIA | JUDGMENT_CRITERIA


def kpi_reading_count(goal: Goal, kpis: KPIRegistry) -> int:
    """Total revenue/cost readings recorded for this goal so far."""
    return len(kpis.history(f"revenue_{goal.id}")) + len(kpis.history(f"cost_{goal.id}"))


def maturity(goal: Goal, kpis: KPIRegistry, sample: int = MATURITY_SAMPLE) -> float:
    """How much to trust measured data over the founder's estimate — saturating,
    same shape as SimplePrioritizer's urgency term."""
    return min(kpi_reading_count(goal, kpis) / sample, 1.0)


def measured_value(goal: Goal, kpis: KPIRegistry, criterion: str) -> float | None:
    """KPI-derived value for a measurable criterion, or None when no measurement
    exists yet (or the criterion has no measured counterpart at all)."""
    if criterion == "expected_revenue":
        return kpis.latest(f"revenue_{goal.id}")
    if criterion == "required_investment":
        return kpis.latest(f"cost_{goal.id}")
    if criterion == "time_to_first_profit":
        return _measured_time_to_first_profit(goal, kpis)
    return None


def blended(goal: Goal, kpis: KPIRegistry, criterion: str) -> float | None:
    """Founder estimate and measured value combined, weighted by maturity — the
    founder's original guess smoothly loses influence as real data accumulates,
    never a hard cutover. Judgment-only criteria fall straight through to the
    founder estimate since measured_value has nothing to offer them.

    Returns None when there is genuinely no information at all (no founder
    estimate, no measurement) — callers must not default a missing value to
    0.0 themselves, since 0.0 reads as "zero cost" / "instant profit" and would
    unfairly favor an unscored goal on inverted (lower-is-better) criteria.
    """
    founder = goal.founder_estimate.get(criterion)
    measured = measured_value(goal, kpis, criterion)
    if founder is None and measured is None:
        return None
    if measured is None:
        return founder
    if founder is None:
        return measured
    weight = maturity(goal, kpis)
    return (1 - weight) * founder + weight * measured


def _measured_time_to_first_profit(goal: Goal, kpis: KPIRegistry) -> float | None:
    """Days from goal creation to the first revenue reading that exceeded the
    most recently known cost as of that time. Revenue/cost readings are treated
    as cumulative-to-date snapshots (matching the existing KPI convention, e.g.
    KPIRegistry.delta), not per-period deltas."""
    revenue_history = kpis.history(f"revenue_{goal.id}")
    cost_history = kpis.history(f"cost_{goal.id}")
    if not revenue_history:
        return None

    created = datetime.fromisoformat(goal.created_at)
    for entry in sorted(revenue_history, key=lambda e: e["at"]):
        cost_as_of = _latest_at_or_before(cost_history, entry["at"])
        if entry["value"] > cost_as_of:
            reached = datetime.fromisoformat(entry["at"])
            return (reached - created).total_seconds() / 86400
    return None


def _latest_at_or_before(history: list[dict], at: str) -> float:
    candidates = sorted((h for h in history if h["at"] <= at), key=lambda h: h["at"])
    return candidates[-1]["value"] if candidates else 0.0
