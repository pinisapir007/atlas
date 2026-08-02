from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal
from atlas.brain.valuation import blended

# (criterion, invert) — invert=True means lower raw values are better (cost, time-to-profit).
CASH_FLOW_CRITERIA = (
    ("expected_revenue", False),
    ("required_investment", True),
    ("time_to_first_profit", True),
)
STRATEGIC_VALUE_CRITERIA = (
    ("scalability", False),
    ("automation_potential", False),
    ("long_term_strategic_value", False),
)


def score_cash_flow(goal: Goal, all_active_goals: list[Goal], kpis: KPIRegistry) -> float:
    """Near-term cash-flow potential, ranked only against other goals sharing
    this goal's horizon — a long-term asset-building goal is never penalized
    for paying slower than a short-term cash goal, because it's never compared
    to one here."""
    return _score(goal, all_active_goals, kpis, CASH_FLOW_CRITERIA)


def score_strategic_value(goal: Goal, all_active_goals: list[Goal], kpis: KPIRegistry) -> float:
    """Long-term/structural value, ranked only against other goals sharing this
    goal's horizon. Kept independent of score_cash_flow by construction — a
    goal's rank on one axis never leaks into the other."""
    return _score(goal, all_active_goals, kpis, STRATEGIC_VALUE_CRITERIA)


def _score(goal: Goal, all_active_goals: list[Goal], kpis: KPIRegistry, criteria) -> float:
    cohort = [g for g in all_active_goals if g.horizon == goal.horizon]
    if goal.id not in {g.id for g in cohort}:
        cohort = [*cohort, goal]
    components = [_normalized(goal, cohort, kpis, criterion, invert) for criterion, invert in criteria]
    return sum(components) / len(components)


def _normalized(goal: Goal, cohort: list[Goal], kpis: KPIRegistry, criterion: str, invert: bool) -> float:
    values = {g.id: v for g in cohort if (v := blended(g, kpis, criterion)) is not None}
    if goal.id not in values or len(values) == 1:
        return 0.5  # no data for this goal on this criterion, or nothing to compare it against
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return 0.5  # nothing to discriminate on within this cohort — neutral default
    position = (values[goal.id] - lo) / (hi - lo)
    return (1 - position) if invert else position
