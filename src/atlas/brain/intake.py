from atlas.brain.models import Task
from atlas.core.registry import Registry, UnsupportedVerb

RESEARCH_CATEGORY = "discover_opportunities"
_ABSORBED_MARKER = "absorbed "


def absorb_opportunities(tasks: list[Task], registry: Registry, memory) -> list[Task]:
    """Bridge between Research and Revenue: turns a completed discovery
    task's reported opportunities into follow-on Tasks under the same
    goal, each carrying the channel category Research suggested (or
    "create_asset" when no existing channel fits — the existing
    structural-proposal path in Delegator/RiskPolicy already routes that
    to a human, so no new gating logic is needed here).

    Idempotent — a given research task's opportunities are only absorbed
    once, tracked via a history entry rather than a new Task field.
    """
    new_tasks: list[Task] = []
    for task in tasks:
        if task.category != RESEARCH_CATEGORY or task.status != "done":
            continue
        if _already_absorbed(task):
            continue

        opportunities = _fetch_opportunities(task, registry)
        for opportunity in opportunities:
            new_tasks.append(
                Task(
                    goal_id=task.goal_id,
                    description=opportunity.get("description", ""),
                    category=opportunity.get("suggested_category", "create_asset"),
                    reversible=True,
                )
            )

        task.transition(task.status, f"{_ABSORBED_MARKER}{len(opportunities)} opportunities")
        memory.save_task(task)

    return new_tasks


def _fetch_opportunities(task: Task, registry: Registry) -> list[dict]:
    if not task.assigned_asset_id:
        return []
    try:
        report = registry.dispatch(task.assigned_asset_id, "report")
    except UnsupportedVerb:
        return []
    if not isinstance(report, dict):
        return []
    return report.get("opportunities", [])


def _already_absorbed(task: Task) -> bool:
    return any(entry.get("reason", "").startswith(_ABSORBED_MARKER) for entry in task.history)
