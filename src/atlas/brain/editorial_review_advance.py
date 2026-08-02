from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

EDITORIAL_ASSET_ID = "editorial_review"
EDITORIAL_CATEGORY = "editorial_review"
# Deliberately distinct from "content_factory" (Mission 006's founder-
# rejection regenerate-trigger category) — both are reversible=True tasks
# targeting the same asset, and content_factory_advance's dedup counting
# would otherwise conflate an editorial fix with a founder-rejection
# regenerate, breaking both cycles' bookkeeping.
CONTENT_FACTORY_FIX_CATEGORY = "content_factory_editorial_fix"


def _latest_content_packaged_at(opportunity: dict) -> str:
    """Timestamp of the most recent transition into 'content_packaged' —
    marks the start of the current content generation, so fix-request tasks
    from a prior (now-discarded) generation aren't miscounted against it."""
    timestamps = [h["at"] for h in opportunity.get("history", []) if h.get("stage") == "content_packaged"]
    return max(timestamps) if timestamps else ""


def advance_editorial_review(tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry) -> list[Task]:
    """Editorial-Review-specific continuation — the fifth application of the
    same bridge pattern (Recruitment, Affiliate Department, Affiliate
    Intelligence, Content Factory). Three responsibilities:

    1. Trigger evaluation once a package exists and hasn't been judged yet.
    2. When revision is required, dispatch a fix request to Content Factory
       (cross-asset, same category-tagged Task mechanism every dispatch
       already uses — not a new inter-asset call).
    3. When Editorial Review gives up (reject, or 2 cycles exhausted),
       notify the founder — reusing the existing approve/reject mechanism
       as a pure acknowledgment, not a new notification system.
    """
    try:
        report = registry.dispatch(EDITORIAL_ASSET_ID, "report")
    except (UnsupportedVerb, KeyError):
        return []
    if not isinstance(report, dict):
        return []

    opportunities = report.get("opportunities")
    if not isinstance(opportunities, list):
        return []

    known_goal_ids = {g.id for g in memory.goals()}
    new_tasks: list[Task] = []

    new_tasks.extend(_trigger_review(opportunities, tasks, known_goal_ids))
    new_tasks.extend(_trigger_fix(opportunities, tasks, known_goal_ids))
    new_tasks.extend(_notify_founder_of_abandonment(opportunities, tasks, known_goal_ids, kpis))

    return new_tasks


def _trigger_review(opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    needs_review_goal_ids = {
        o.get("goal_id")
        for o in opportunities
        if isinstance(o, dict)
        and o.get("stage") == "content_packaged"
        and not o.get("editorial_verdict")
        and o.get("goal_id") in known_goal_ids
    }
    open_nudge_goal_ids = {
        t.goal_id
        for t in tasks
        if t.category == EDITORIAL_CATEGORY and t.source_opportunity_id is None and t.status in OPEN_STATUSES
    }
    return [
        Task(
            goal_id=goal_id,
            description="Run editorial review on the generated content package",
            category=EDITORIAL_CATEGORY,
            reversible=True,
        )
        for goal_id in needs_review_goal_ids - open_nudge_goal_ids
    ]


def _trigger_fix(opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    new_tasks: list[Task] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or opportunity.get("stage") != "content_packaged":
            continue
        if opportunity.get("editorial_verdict") != "revision_required":
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        opportunity_id = opportunity.get("id")
        if not opportunity_id:
            continue

        cycles = opportunity.get("editorial_cycles", 0)
        # Only count fix-request tasks made against the CURRENT content
        # generation, not all-time. A founder-rejection regeneration
        # (Content Factory's _generate()) resets editorial_cycles to 0 and
        # re-transitions to "content_packaged", but old fix-request tasks
        # from a prior generation still exist in history — counting those
        # against the new, reset cycle count was the bug: it made the dedup
        # check think this cycle's fix was already requested when it was
        # actually requested for content that no longer exists.
        since = _latest_content_packaged_at(opportunity)
        fix_trigger_count = sum(
            1
            for t in tasks
            if t.source_opportunity_id == opportunity_id
            and t.category == CONTENT_FACTORY_FIX_CATEGORY
            and t.created_at >= since
        )
        if fix_trigger_count >= cycles:
            continue  # this cycle's fix has already been requested

        failed_sections = opportunity.get("editorial_feedback", {}).get("failed_sections", [])
        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=f"Fix failed sections per editorial feedback: {failed_sections}",
                category=CONTENT_FACTORY_FIX_CATEGORY,  # dispatches to Content Factory, not back to Editorial Review
                reversible=True,
                source_opportunity_id=opportunity_id,
            )
        )
    return new_tasks


def _notify_founder_of_abandonment(opportunities: list, tasks: list[Task], known_goal_ids: set, kpis: KPIRegistry) -> list[Task]:
    already_notified_ids = {t.source_opportunity_id for t in tasks if t.source_opportunity_id is not None}

    new_tasks: list[Task] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or opportunity.get("stage") != "lost":
            continue
        if opportunity.get("editorial_verdict") != "reject":
            continue  # "lost" for another reason (e.g. founder rejected twice) — not Editorial Review's notification to send
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        opportunity_id = opportunity.get("id")
        if not opportunity_id or opportunity_id in already_notified_ids:
            continue

        current = kpis.latest(f"campaigns_abandoned_by_editorial_{goal_id}") or 0.0
        kpis.record(f"campaigns_abandoned_by_editorial_{goal_id}", current + 1.0)

        product_name = opportunity.get("product_name", opportunity_id)
        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=(
                    f"Notice: campaign for '{product_name}' was abandoned — failed editorial review after "
                    f"{opportunity.get('editorial_cycles', 0)} revision cycle(s). No action is required; "
                    "approve to acknowledge."
                ),
                category=EDITORIAL_CATEGORY,
                reversible=False,  # still routed through the standard founder-visibility gate, even though it's informational
                source_opportunity_id=opportunity_id,
            )
        )
    return new_tasks
