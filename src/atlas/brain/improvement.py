from datetime import datetime, timedelta, timezone

from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import Goal, Task

MIN_SAMPLE = 3
SUCCESS_RATE_THRESHOLD = 0.5
DEFAULT_COOLDOWN_DAYS = 30
RESOLVED_STATUSES = {"done", "failed", "blocked", "rejected"}


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
        history = kpis.history(name)
        if len(history) < 3:
            continue
        if history[-1]["value"] > history[-3]["value"]:
            continue  # improved over its last two readings — no evidence of a problem
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
        redesign_category = "redesign_workflow"
        if _in_cooldown(redesign_category, existing_tasks, cooldown_days):
            continue
        candidates.append(
            Task(
                goal_id=goal_id,
                description=f"Task category '{category}' succeeded only {success}/{sample} times",
                category=redesign_category,
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
