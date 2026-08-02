from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

AFFILIATE_ASSET_ID = "affiliate_department"
AFFILIATE_CATEGORY = "affiliate_pipeline"

# Opportunity stages the department still has internal work to do on —
# discover -> evaluate -> plan_content are all internal, non-founder-gated
# steps. "content_planned" and "lost" are excluded: content_planned is
# handled separately below (it needs a founder-approval request, not another
# internal nudge), and "lost" is terminal.
IN_PROGRESS_STAGES = {"discovered", "selected"}

# Deterministic, documented projection constants — never real tracked data.
# ASSUMED_MONTHLY_LEADS and PLACEHOLDER_CTR are stated assumptions, not
# fabricated numbers dressed up as measurements. See
# docs/FIRST_REVENUE_PIPELINE.md for the reasoning.
ASSUMED_MONTHLY_LEADS = 500
PLACEHOLDER_CTR = 0.03


def advance_affiliate_pipeline(tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry) -> list[Task]:
    """Affiliate-Department-specific continuation, mirroring
    atlas.brain.pipeline_advance's shape for Recruitment, in two parts:

    1. Keeps nudging the department forward (discover -> evaluate -> plan
       content) for any goal that still has in-progress opportunities — one
       open "keep going" task per goal at a time, since the agent itself
       decides what its next internal step is from its own state.
    2. Once an opportunity reaches content_planned, records its projected
       (never real) KPIs and requests founder approval exactly once — never
       a second time for the same opportunity, regardless of whether that
       first request is still pending, approved, or rejected, since nothing
       past the approval gate (Published/Tracking) exists yet to re-request
       against.
    """
    try:
        report = registry.dispatch(AFFILIATE_ASSET_ID, "report")
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
    new_tasks.extend(_request_founder_approval(opportunities, tasks, known_goal_ids, kpis))

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
        if t.category == AFFILIATE_CATEGORY and t.source_opportunity_id is None and t.status in OPEN_STATUSES
    }
    return [
        Task(
            goal_id=goal_id,
            description="Continue affiliate pipeline (discovery, evaluation, or content planning)",
            category=AFFILIATE_CATEGORY,
            reversible=True,
        )
        for goal_id in in_progress_goal_ids - open_nudge_goal_ids
    ]


def _request_founder_approval(opportunities: list, tasks: list[Task], known_goal_ids: set, kpis: KPIRegistry) -> list[Task]:
    already_requested_ids = {t.source_opportunity_id for t in tasks if t.source_opportunity_id is not None}

    new_tasks: list[Task] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict):
            continue
        if opportunity.get("stage") != "content_planned":
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue  # no goal to attribute to, or not tracked by this brain — never fall back
        opportunity_id = opportunity.get("id")
        if not opportunity_id or opportunity_id in already_requested_ids:
            continue  # approval already requested once for this opportunity — never repeat it

        _record_projected_kpis(opportunity, goal_id, kpis)

        product_name = opportunity.get("product_name", opportunity_id)
        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=f"Founder approval requested: publish affiliate campaign for {product_name}",
                category=AFFILIATE_CATEGORY,
                reversible=False,  # publishing is not reversible — RiskPolicy routes this straight to pending_approval
                source_opportunity_id=opportunity_id,
            )
        )
    return new_tasks


def _record_projected_kpis(opportunity: dict, goal_id: str, kpis: KPIRegistry) -> None:
    estimated_conversion = opportunity.get("estimated_conversion", 0.0)
    commission = opportunity.get("commission_per_conversion", 0.0)
    competition = opportunity.get("competition", 0.0)
    content_difficulty = opportunity.get("content_difficulty", 0.0)

    # Deliberately NOT written to revenue_<goal_id>/cost_<goal_id> — those
    # names are reserved for real, kpi_intake-attributed measurements. Mixing
    # a projection into that series would let the Strategist's confidence
    # blending mistake an estimate for verified data, exactly the "false
    # zero cost" class of bug already found and fixed once this session.
    kpis.record(f"expected_ctr_{goal_id}", PLACEHOLDER_CTR)
    kpis.record(f"expected_conversion_{goal_id}", estimated_conversion)
    kpis.record(f"expected_revenue_{goal_id}", estimated_conversion * commission * ASSUMED_MONTHLY_LEADS)
    kpis.record(f"risk_score_{goal_id}", (competition + content_difficulty) / 2)
