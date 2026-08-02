from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, Task
from atlas.core.registry import Registry, UnsupportedVerb

RESEARCH_CATEGORY = "discover_opportunities"
_ABSORBED_MARKER = "absorbed "


def absorb_opportunities(tasks: list[Task], registry: Registry, memory, knowledge: KnowledgeBase) -> list[Task]:
    """Bridge between Research and Revenue: turns a completed discovery
    task's reported opportunities into follow-on Tasks under the same
    goal, each carrying the channel category Research suggested (or
    "create_asset" when no existing channel fits — the existing
    structural-proposal path in Delegator/RiskPolicy already routes that
    to a human, so no new gating logic is needed here).

    Also records every opportunity as a durable Finding in the
    KnowledgeBase, independent of the Task it produces — a channel with no
    dispatchable asset yet (e.g. "youtube", "ugc") still gets remembered
    instead of only living as long as its "create_asset" Task does.

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
            category = opportunity.get("suggested_category", "create_asset")
            description = opportunity.get("description", "")
            # assigned_asset_id is whichever asset actually produced this
            # research task's report — "research" today, but this doesn't
            # hardcode that, since RESEARCH_CATEGORY isn't tied to one asset.
            knowledge.save_finding(
                Finding(
                    source=task.assigned_asset_id or "research",
                    category=category,
                    description=description,
                    evidence=opportunity.get("evidence", ""),
                )
            )
            new_tasks.append(
                Task(
                    goal_id=task.goal_id,
                    description=description,
                    category=category,
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
