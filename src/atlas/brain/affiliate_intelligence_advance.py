from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

AFFILIATE_INTELLIGENCE_ASSET_ID = "affiliate_intelligence"
AFFILIATE_INTELLIGENCE_CATEGORY = "affiliate_intelligence"

# discovered/researched are internal, non-founder-gated steps; "ranked" is
# excluded here — it's handled separately below, since it needs a founder
# choice, not another internal nudge.
IN_PROGRESS_STAGES = {"discovered", "researched"}


def advance_affiliate_intelligence(tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry) -> list[Task]:
    """Affiliate-Intelligence-specific continuation, mirroring the shape of
    atlas.brain.affiliate_pipeline_advance (Mission 003) and
    atlas.brain.pipeline_advance (Recruitment) — the same pattern applied a
    third time, not a fourth kind of mechanism:

    1. Keeps nudging the department forward (discover -> research -> rank)
       for any goal with in-progress opportunities — one open "keep going"
       task per goal.
    2. Once ranking is complete for a goal (every opportunity reached
       "ranked"), creates one founder-approval task PER ranked opportunity,
       asking the founder to choose which to pursue — reusing the existing
       binary approve/reject mechanism per task rather than inventing a
       multi-choice approval system. Never repeats a request for the same
       opportunity once one has ever been created for it.
    """
    try:
        report = registry.dispatch(AFFILIATE_INTELLIGENCE_ASSET_ID, "report")
    except (UnsupportedVerb, KeyError):
        return []
    if not isinstance(report, dict):
        return []

    opportunities = report.get("opportunities")
    if not isinstance(opportunities, list):
        return []

    known_goal_ids = {g.id for g in memory.goals()}
    new_tasks: list[Task] = []

    new_tasks.extend(_continue_in_progress_goals(opportunities, tasks, known_goal_ids))
    new_tasks.extend(_request_founder_choice(opportunities, tasks, known_goal_ids, kpis))

    return new_tasks


def _continue_in_progress_goals(opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    in_progress_goal_ids = {
        o.get("goal_id")
        for o in opportunities
        if isinstance(o, dict) and o.get("stage") in IN_PROGRESS_STAGES and o.get("goal_id") in known_goal_ids
    }
    open_nudge_goal_ids = {
        t.goal_id
        for t in tasks
        if t.category == AFFILIATE_INTELLIGENCE_CATEGORY and t.source_opportunity_id is None and t.status in OPEN_STATUSES
    }
    return [
        Task(
            goal_id=goal_id,
            description="Continue affiliate intelligence pipeline (discovery, research, or ranking)",
            category=AFFILIATE_INTELLIGENCE_CATEGORY,
            reversible=True,
        )
        for goal_id in in_progress_goal_ids - open_nudge_goal_ids
    ]


def _request_founder_choice(opportunities: list, tasks: list[Task], known_goal_ids: set, kpis: KPIRegistry) -> list[Task]:
    already_requested_ids = {t.source_opportunity_id for t in tasks if t.source_opportunity_id is not None}

    # Only ask once ranking is fully complete for a goal — a partial ranked
    # set (some opportunities still discovered/researched) isn't a real
    # choice yet.
    by_goal: dict[str, list[dict]] = {}
    for opportunity in opportunities:
        if not isinstance(opportunity, dict):
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        by_goal.setdefault(goal_id, []).append(opportunity)

    new_tasks: list[Task] = []
    for goal_id, goal_opportunities in by_goal.items():
        if not goal_opportunities or any(o.get("stage") != "ranked" for o in goal_opportunities):
            continue

        kpis.record(f"opportunities_ranked_{goal_id}", float(len(goal_opportunities)))

        for opportunity in sorted(goal_opportunities, key=lambda o: o.get("score", 0.0), reverse=True):
            opportunity_id = opportunity.get("id")
            if not opportunity_id or opportunity_id in already_requested_ids:
                continue
            product_name = opportunity.get("product_name", opportunity_id)
            score = opportunity.get("score", 0.0)
            new_tasks.append(
                Task(
                    goal_id=goal_id,
                    description=(
                        f"Founder choice requested: pursue affiliate opportunity '{product_name}' "
                        f"(score {score:.4f})? Approve this task to choose it."
                    ),
                    category=AFFILIATE_INTELLIGENCE_CATEGORY,
                    reversible=False,  # a real business commitment — RiskPolicy routes this to pending_approval
                    source_opportunity_id=opportunity_id,
                )
            )
    return new_tasks
