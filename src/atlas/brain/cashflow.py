from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal

# "Profit: Not separately tracked — computable as revenue minus cost
# wherever both are live" (docs/ATLAS_BUSINESS_BLUEPRINT.md §9). Pure,
# side-effect-free, like valuation.py/scoring.py — reads real revenue_*/
# cost_* KPI readings only, never a founder estimate. Returns None (never
# 0.0) when either side is unmeasured, so an unmeasured goal never reads as
# "zero cost" / "break-even" — the same fail-closed rule kpi_intake and
# valuation already enforce.


def profit(goal: Goal, kpis: KPIRegistry) -> float | None:
    revenue = kpis.latest(f"revenue_{goal.id}")
    cost = kpis.latest(f"cost_{goal.id}")
    if revenue is None or cost is None:
        return None
    return revenue - cost


def roi(goal: Goal, kpis: KPIRegistry) -> float | None:
    """Return on investment: profit / cost. None when cost is unmeasured or
    zero — a zero-cost goal has undefined ROI, not infinite ROI."""
    cost = kpis.latest(f"cost_{goal.id}")
    p = profit(goal, kpis)
    if p is None or not cost:
        return None
    return p / cost


def goal_cash_flow(goals: list[Goal], kpis: KPIRegistry) -> list[dict]:
    """One entry per goal with at least revenue or cost measured — the
    shared shape used by both the executive report (Reporter) and the live
    console (atlas console / REPL status), so the two never drift apart."""
    entries = []
    for goal in goals:
        revenue = kpis.latest(f"revenue_{goal.id}")
        cost = kpis.latest(f"cost_{goal.id}")
        if revenue is None and cost is None:
            continue
        entries.append(
            {
                "goal_id": goal.id,
                "description": goal.description,
                "revenue": revenue,
                "cost": cost,
                "profit": profit(goal, kpis),
                "roi": roi(goal, kpis),
            }
        )
    return entries
