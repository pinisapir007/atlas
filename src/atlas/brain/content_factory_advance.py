from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

CONTENT_FACTORY_ASSET_ID = "content_factory"
CONTENT_FACTORY_CATEGORY = "content_factory"


def advance_content_factory(
    tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry, campaign_claimed_goal_ids: set | None = None
) -> list[Task]:
    """Content-Factory-specific continuation — the fourth application of the
    same bridge pattern used for Recruitment, the Affiliate Department, and
    Affiliate Intelligence. Three responsibilities:

    1. Trigger the first generation once an opportunity is selected_for_marketing.
    2. Request founder review once a package exists — one task, reversible=False.
    3. Handle a rejected review as "request changes": regenerate once, then
       permanently abandon the opportunity on a second rejection. This is
       Approve/Reject/Request-changes expressed entirely through the
       existing binary approve()/reject() primitive, counted over time —
       not a new multi-choice approval mechanism.

    `campaign_claimed_goal_ids` (2026-08-03): goals already claimed by the
    newer Campaign/Execution Orchestrator pipeline (see
    campaign_advance.py) — `selected_for_marketing` is the same real
    signal both pipelines would otherwise race on, since both exist to
    turn a founder-chosen product into approved content. Excluding a
    claimed goal from `_trigger_generation` here is what keeps the two
    pipelines from double-generating content and double-requesting
    founder approval for the same opportunity. Optional, defaults to
    "nothing claimed" — every existing caller/test keeps its exact prior
    behavior; this only changes anything once a goal is actually claimed.
    """
    try:
        report = registry.dispatch(CONTENT_FACTORY_ASSET_ID, "report")
    except (UnsupportedVerb, KeyError):
        return []
    if not isinstance(report, dict):
        return []

    opportunities = report.get("opportunities")
    if not isinstance(opportunities, list):
        return []

    known_goal_ids = {g.id for g in memory.goals()} - (campaign_claimed_goal_ids or set())
    new_tasks: list[Task] = []

    new_tasks.extend(_trigger_generation(opportunities, tasks, known_goal_ids))
    new_tasks.extend(_request_review(opportunities, tasks, known_goal_ids, kpis))
    new_tasks.extend(_handle_rejections(opportunities, tasks, known_goal_ids))

    return new_tasks


def _trigger_generation(opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    needs_generation_goal_ids = {
        o.get("goal_id")
        for o in opportunities
        if isinstance(o, dict)
        and o.get("stage") == "selected_for_marketing"
        and not o.get("content_package")
        and o.get("goal_id") in known_goal_ids
    }
    open_nudge_goal_ids = {
        t.goal_id
        for t in tasks
        if t.category == CONTENT_FACTORY_CATEGORY and t.source_opportunity_id is None and t.status in OPEN_STATUSES
    }
    return [
        Task(
            goal_id=goal_id,
            description="Generate the content package for the selected affiliate opportunity",
            category=CONTENT_FACTORY_CATEGORY,
            reversible=True,
        )
        for goal_id in needs_generation_goal_ids - open_nudge_goal_ids
    ]


def _request_review(opportunities: list, tasks: list[Task], known_goal_ids: set, kpis: KPIRegistry) -> list[Task]:
    # Gated on "editorial_passed", not raw "content_packaged" — Editorial
    # Review must clear a package before the founder ever sees it.
    new_tasks: list[Task] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or opportunity.get("stage") != "editorial_passed":
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        opportunity_id = opportunity.get("id")
        if not opportunity_id:
            continue

        review_count = _count(tasks, opportunity_id, reversible=False)
        regenerate_count = _count(tasks, opportunity_id, reversible=True)
        if review_count != regenerate_count:
            continue  # a review for the latest package is already open or was already requested

        current = kpis.latest(f"content_packages_generated_{goal_id}") or 0.0
        kpis.record(f"content_packages_generated_{goal_id}", current + 1.0)

        product_name = opportunity.get("product_name", opportunity_id)
        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=(
                    f"Founder review requested: content package ready for '{product_name}'. "
                    "Approve to accept it, or reject to request changes (a second rejection abandons this opportunity)."
                ),
                category=CONTENT_FACTORY_CATEGORY,
                reversible=False,  # a real content/marketing commitment — RiskPolicy routes this to pending_approval
                source_opportunity_id=opportunity_id,
            )
        )
    return new_tasks


def _handle_rejections(opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    # A founder rejection doesn't change the opportunity's stage — it's
    # still "editorial_passed" until the regenerate-trigger actually runs.
    new_tasks: list[Task] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or opportunity.get("stage") != "editorial_passed":
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        opportunity_id = opportunity.get("id")
        if not opportunity_id:
            continue

        failed_review_count = _count(tasks, opportunity_id, reversible=False, status="failed")
        regenerate_count = _count(tasks, opportunity_id, reversible=True)
        if failed_review_count <= regenerate_count:
            continue  # every rejection so far already has a regenerate-trigger

        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=f"Regenerate content package for '{opportunity.get('product_name', opportunity_id)}' after founder-requested changes",
                category=CONTENT_FACTORY_CATEGORY,
                reversible=True,
                source_opportunity_id=opportunity_id,
            )
        )
    return new_tasks


def _count(tasks: list[Task], opportunity_id: str, reversible: bool, status: str | None = None) -> int:
    return sum(
        1
        for t in tasks
        if t.source_opportunity_id == opportunity_id
        and t.category == CONTENT_FACTORY_CATEGORY
        and t.reversible is reversible
        and (status is None or t.status == status)
    )
