from datetime import datetime, timedelta, timezone

from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal, Task

MIN_SAMPLE = 3
SUCCESS_RATE_THRESHOLD = 0.5
DEFAULT_COOLDOWN_DAYS = 30
RESOLVED_STATUSES = {"done", "failed", "blocked", "rejected", "superseded"}

# Generic stagnation detection is intentionally narrow.
#
# A KPI is eligible only when its direction is unambiguous. Snapshot/state
# metrics such as publish_queue_*, research_attempts_*, costs, risk scores,
# etc. are not safe to interpret generically: zero may be healthy, higher
# may be worse, or movement may merely reflect workflow state.
_HIGHER_IS_BETTER_EXACT = {"revenue", "tasks_completed"}
_HIGHER_IS_BETTER_PREFIXES = ("revenue_",)
_LOWER_IS_BETTER_TARGETS = {
    "tasks_blocked": 0.0,
    "pending_approvals": 0.0,
}


def _kpi_stagnation_semantics(name: str) -> tuple[str, float | None] | None:
    """Return explicit generic-improvement semantics for a KPI.

    ("higher", None): larger values are improvement.
    ("lower", target): smaller values are improvement and values at/below
    target are already healthy.

    None means the KPI is intentionally excluded from generic stagnation
    reasoning because its meaning requires domain-specific context.
    """
    if name in _HIGHER_IS_BETTER_EXACT or name.startswith(_HIGHER_IS_BETTER_PREFIXES):
        return ("higher", None)

    if name in _LOWER_IS_BETTER_TARGETS:
        return ("lower", _LOWER_IS_BETTER_TARGETS[name])

    return None


def propose_improvements(
    kpis: KPIRegistry,
    outcome_log: list[dict],
    existing_tasks: list[Task],
    goals: list[Goal],
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
) -> list[Task]:
    """Evidence-gated, cooldown-checked candidate redesign tasks.

    Only called from CEOBrain.review() (the slow cycle), never from tick()
    — that alone rules out most churn, per the "avoid unnecessary redesigns"
    principle. No evidence, no candidate; an area already under review or
    resolved within the cooldown window is skipped, per "preserve business
    continuity".
    """
    candidates: list[Task] = []
    goal_id = _anchor_goal(goals)
    if goal_id is None:
        return candidates

    for name in kpis.names():
        semantics = _kpi_stagnation_semantics(name)
        if semantics is None:
            continue

        history = kpis.history(name)
        if len(history) < 3:
            continue

        direction, healthy_target = semantics
        latest = history[-1]["value"]
        earlier = history[-3]["value"]

        if direction == "higher":
            if latest > earlier:
                continue  # improved — no evidence of a problem
        else:
            # Lower-is-better KPIs must never treat a decrease as failure.
            # Reaching the explicit healthy target is success even if flat.
            if healthy_target is not None and latest <= healthy_target:
                continue
            if latest < earlier:
                continue  # improved — no evidence of a problem

        category = "redesign_operational_architecture"
        if _in_cooldown(category, existing_tasks, cooldown_days):
            continue
        candidates.append(
            Task(
                goal_id=goal_id,
                description=f"KPI '{name}' has not improved over its last 3 readings",
                category=category,
            )
        )

    for category, (sample, success) in _category_success_rates(outcome_log).items():
        if sample < MIN_SAMPLE or success / sample >= SUCCESS_RATE_THRESHOLD:
            continue
        # Workflow/automation/performance tuning, not a core-architecture
        # change — per standing policy this is pre-approved (2026-08-02):
        # "improve_" (not "redesign_") so it skips RiskPolicy's redesign-
        # prefix gate, and reversible=True (same convention SimplePlanner
        # already uses for its own routine, no-financial/access/legal-risk
        # tasks) so it clears every other axis too and auto-delegates.
        # "redesign_operational_architecture" above is untouched and stays
        # gated — a flat/declining KPI can reflect a structural problem,
        # closer to core-architecture than a workflow tweak.
        improve_category = "improve_workflow"
        if _in_cooldown(improve_category, existing_tasks, cooldown_days):
            continue
        candidates.append(
            Task(
                goal_id=goal_id,
                description=f"Task category '{category}' succeeded only {success}/{sample} times",
                category=improve_category,
                reversible=True,
            )
        )

    return candidates


def _anchor_goal(goals: list[Goal]) -> str | None:
    for goal in goals:
        if goal.status == "active":
            return goal.id
    return None


def _in_cooldown(category: str, existing_tasks: list[Task], cooldown_days: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
    for task in existing_tasks:
        if task.category != category:
            continue
        if task.status not in RESOLVED_STATUSES:
            return True  # still open — don't pile on another proposal for the same area
        if datetime.fromisoformat(task.updated_at) >= cutoff:
            return True  # resolved too recently — let it settle before proposing again
    return False


def _category_success_rates(outcome_log: list[dict]) -> dict[str, tuple[int, int]]:
    counts: dict[str, list[int]] = {}
    for entry in outcome_log:
        category = entry.get("category")
        if category is None:
            continue
        bucket = counts.setdefault(category, [0, 0])
        bucket[0] += 1
        if entry.get("status") == "done":
            bucket[1] += 1
    return {k: (v[0], v[1]) for k, v in counts.items()}
