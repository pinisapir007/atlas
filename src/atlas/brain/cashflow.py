from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal

# "Profit: Not separately tracked — computable as revenue minus cost
# wherever both are live" (docs/ATLAS_BUSINESS_BLUEPRINT.md §9). Pure,
# side-effect-free, like valuation.py/scoring.py — reads real revenue_*/
# cost_* KPI readings only, never a founder estimate. Returns None (never
# 0.0) when either side is unmeasured, so an unmeasured goal never reads as
# "zero cost" / "break-even" — the same fail-closed rule kpi_intake and
# valuation already enforce.


def _latest(name: str, kpis: KPIRegistry, snapshot: dict[str, list[dict]] | None = None) -> float | None:
    if snapshot is None:
        return kpis.latest(name)
    history = snapshot.get(name, [])
    return history[-1]["value"] if history else None


def profit(goal: Goal, kpis: KPIRegistry, snapshot: dict[str, list[dict]] | None = None) -> float | None:
    revenue = _latest(f"revenue_{goal.id}", kpis, snapshot)
    cost = _latest(f"cost_{goal.id}", kpis, snapshot)
    if revenue is None or cost is None:
        return None
    return revenue - cost


def roi(goal: Goal, kpis: KPIRegistry, snapshot: dict[str, list[dict]] | None = None) -> float | None:
    """Return on investment: profit / cost. None when cost is unmeasured or
    zero — a zero-cost goal has undefined ROI, not infinite ROI."""
    cost = _latest(f"cost_{goal.id}", kpis, snapshot)
    p = profit(goal, kpis, snapshot)
    if p is None or not cost:
        return None
    return p / cost


def goal_cash_flow(
    goals: list[Goal],
    kpis: KPIRegistry,
    snapshot: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """One entry per goal with at least revenue or cost measured — the
    shared shape used by both the executive report (Reporter) and the live
    console (atlas console / REPL status), so the two never drift apart.

    `settled` (real cash verified received, from record_manual_settlement())
    is included for visibility alongside `revenue` (claimed) — deliberately
    not blended into `profit`/`roi`, which stay on the claimed basis
    confidence_score() already reads; a goal can show real profit on paper
    while `settled` reveals none of it has actually been paid out yet."""
    entries = []
    for goal in goals:
        revenue = _latest(f"revenue_{goal.id}", kpis, snapshot)
        cost = _latest(f"cost_{goal.id}", kpis, snapshot)
        settled = _latest(f"settled_{goal.id}", kpis, snapshot)
        if revenue is None and cost is None and settled is None:
            continue
        entries.append(
            {
                "goal_id": goal.id,
                "description": goal.description,
                "revenue": revenue,
                "cost": cost,
                "settled": settled,
                "profit": profit(goal, kpis, snapshot),
                "roi": roi(goal, kpis, snapshot),
            }
        )
    return entries
