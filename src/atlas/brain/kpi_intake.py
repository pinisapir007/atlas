from atlas.brain.kpi import KPIRegistry
from atlas.brain.ledger import Ledger
from atlas.brain.models import LedgerEntry, Task

WON_STAGE = "won"


def record_revenue(task: Task, result, kpis: KPIRegistry, ledger: Ledger | None = None) -> None:
    """Attributes a just-completed dispatch's revenue/cost signal to the
    task's goal, if the result shape is recognized. Fail-closed: an
    unrecognized or malformed shape (Research's, or anything unknown)
    records nothing rather than guessing at a number. `ledger`, when given,
    also gets one LedgerEntry per real amount recorded here — optional so
    every existing caller/test that doesn't pass one keeps working exactly
    as before."""
    if not isinstance(result, dict):
        return
    if "revenue_generated" in result:
        _record_revenue_channel_result(task, result, kpis, ledger)
    elif "opportunities" in result:
        _record_recruitment_result(result, kpis, ledger)


def _record_revenue_channel_result(task: Task, result: dict, kpis: KPIRegistry, ledger: Ledger | None = None) -> None:
    """Revenue's shape: one incremental amount from this one execution —
    accumulate onto the goal's running total."""
    amount = result.get("revenue_generated")
    if not isinstance(amount, (int, float)):
        return
    name = f"revenue_{task.goal_id}"
    current = kpis.latest(name) or 0.0
    kpis.record(name, current + amount)
    if ledger is not None:
        ledger.record(LedgerEntry(goal_id=task.goal_id, kind="revenue_claimed", amount=amount))


def _record_recruitment_result(result: dict, kpis: KPIRegistry, ledger: Ledger | None = None) -> None:
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

    Ledger entries record the *delta* against the last recorded reading,
    and only when it actually changed — a full recomputation runs every
    tick regardless of whether anything real happened, so writing an entry
    unconditionally would spam the ledger with zero-change "events" that
    never occurred.
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
        previous_revenue = kpis.latest(f"revenue_{goal_id}") or 0.0
        previous_cost = kpis.latest(f"cost_{goal_id}") or 0.0
        kpis.record(f"revenue_{goal_id}", goal_totals["revenue"])
        kpis.record(f"cost_{goal_id}", goal_totals["cost"])
        if ledger is not None:
            revenue_delta = goal_totals["revenue"] - previous_revenue
            if revenue_delta != 0.0:
                ledger.record(LedgerEntry(goal_id=goal_id, kind="revenue_claimed", amount=revenue_delta, category="recruitment"))
            cost_delta = goal_totals["cost"] - previous_cost
            if cost_delta != 0.0:
                ledger.record(LedgerEntry(goal_id=goal_id, kind="cost", amount=cost_delta, category="recruitment"))


def record_manual_revenue(
    goal_id: str,
    amount: float,
    cost: float | None,
    kpis: KPIRegistry,
    ledger: Ledger | None = None,
    provider: str = "",
    evidence: str = "",
    document_ref: str = "",
) -> None:
    """A direct, founder-entered revenue reading — for real conversions
    reported by an affiliate network's own dashboard, where no Task dispatch
    result exists to shape-dispatch from (unlike record_revenue() above).
    Same accumulate semantics as _record_revenue_channel_result: one-off
    incremental amount per real conversion, added onto the goal's running
    total — never a replacement reading, since each call reports one more
    real event, not a full recomputation."""
    current_revenue = kpis.latest(f"revenue_{goal_id}") or 0.0
    kpis.record(f"revenue_{goal_id}", current_revenue + amount)
    if ledger is not None:
        ledger.record(
            LedgerEntry(goal_id=goal_id, kind="revenue_claimed", amount=amount, provider=provider, evidence=evidence, document_ref=document_ref)
        )
    if cost is not None:
        current_cost = kpis.latest(f"cost_{goal_id}") or 0.0
        kpis.record(f"cost_{goal_id}", current_cost + cost)
        if ledger is not None:
            ledger.record(
                LedgerEntry(goal_id=goal_id, kind="cost", amount=cost, provider=provider, evidence=evidence, document_ref=document_ref)
            )


def record_manual_cost(
    goal_id: str,
    amount: float,
    kpis: KPIRegistry,
    ledger: Ledger | None = None,
    kind: str = "cost",
    category: str = "",
    provider: str = "",
    evidence: str = "",
    document_ref: str = "",
) -> None:
    """A direct, founder-entered cost reading — for real spend attributable
    to a goal but not tied to any single conversion (ad spend, a tool
    subscription, a platform fee, a one-off setup cost), so it doesn't fit
    record_manual_revenue()'s revenue-plus-optional-cost shape. Same
    accumulate semantics: each call reports one more real, incurred cost,
    added onto the goal's running total — never a replacement reading.

    `kind` defaults to "cost" but accepts "fee" too — a platform/processor
    fee is still a real cost that must net out of profit() the same way,
    just categorized distinctly in the Ledger for audit detail. One
    function, not a near-duplicate `record_manual_fee`, since the KPI-side
    behavior is identical either way."""
    current_cost = kpis.latest(f"cost_{goal_id}") or 0.0
    kpis.record(f"cost_{goal_id}", current_cost + amount)
    if ledger is not None:
        ledger.record(
            LedgerEntry(
                goal_id=goal_id, kind=kind, amount=amount, category=category, provider=provider, evidence=evidence, document_ref=document_ref
            )
        )


def record_manual_settlement(
    goal_id: str,
    amount: float,
    kpis: KPIRegistry,
    ledger: Ledger | None = None,
    provider: str = "",
    evidence: str = "",
    document_ref: str = "",
) -> None:
    """Real cash verified received — distinct from revenue_<goal_id> (a
    claimed conversion, not necessarily paid out yet). Never inferred from
    a claim: absence of a settlement reading means still-claimed, not
    received, the same fail-closed rule every other factor in this system
    already respects. Accumulates onto settled_<goal_id>, a new KPI series
    kept deliberately separate from revenue_<goal_id> rather than
    overwriting it — a business can look profitable on claimed revenue
    while being cash-poor on what has actually settled, and collapsing the
    two would hide that."""
    current_settled = kpis.latest(f"settled_{goal_id}") or 0.0
    kpis.record(f"settled_{goal_id}", current_settled + amount)
    if ledger is not None:
        ledger.record(
            LedgerEntry(goal_id=goal_id, kind="cash_settled", amount=amount, provider=provider, evidence=evidence, document_ref=document_ref)
        )


def record_manual_refund(
    goal_id: str,
    amount: float,
    kpis: KPIRegistry,
    ledger: Ledger | None = None,
    provider: str = "",
    evidence: str = "",
    document_ref: str = "",
) -> None:
    """A real reversal of previously claimed revenue (a refund or
    chargeback) — decrements revenue_<goal_id> directly so
    historical_success_score/measured_outcomes_score reflect what actually
    happened, not the original, now-incorrect claim. Recorded as its own
    ledger kind rather than a negative revenue_claimed entry, so the ledger
    reads as what happened, not as an accounting trick layered onto the
    claim series."""
    current_revenue = kpis.latest(f"revenue_{goal_id}") or 0.0
    kpis.record(f"revenue_{goal_id}", current_revenue - amount)
    if ledger is not None:
        ledger.record(
            LedgerEntry(goal_id=goal_id, kind="refund", amount=amount, provider=provider, evidence=evidence, document_ref=document_ref)
        )
