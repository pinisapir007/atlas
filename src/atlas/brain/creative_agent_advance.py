from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

CREATIVE_AGENT_ASSET_ID = "creative_agent"
CREATIVE_AGENT_CATEGORY = "creative_agent"


def advance_creative_agent(tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry) -> list[Task]:
    """Creative-Agent-specific continuation -- the seventh application of the
    same bridge pattern (Recruitment, Affiliate Department, Affiliate
    Intelligence, Content Factory, Editorial Review, Publishing Gateway).
    One responsibility: trigger a creative-brief draft once an opportunity is
    approved_for_marketing and has no creative_assets yet. No founder-approval
    gate here -- drafting a brief is internal, reversible, zero-cost; the
    real gate lives downstream, in Publishing Gateway, which refuses to build
    a package until a real asset is attached via
    CreativeAgent.attach_real_asset() (a separate, direct founder action, not
    a Task/tick-driven step).
    """
    try:
        report = registry.dispatch(CREATIVE_AGENT_ASSET_ID, "report")
    except (UnsupportedVerb, KeyError):
        return []
    if not isinstance(report, dict):
        return []

    opportunities = report.get("opportunities")
    if not isinstance(opportunities, list):
        return []

    known_goal_ids = {g.id for g in memory.goals()}
    return _trigger_brief(opportunities, tasks, known_goal_ids)


def _trigger_brief(opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    needs_brief_goal_ids = {
        o.get("goal_id")
        for o in opportunities
        if isinstance(o, dict)
        and o.get("stage") == "approved_for_marketing"
        and not o.get("creative_assets")
        and o.get("goal_id") in known_goal_ids
    }
    open_nudge_goal_ids = {
        t.goal_id
        for t in tasks
        if t.category == CREATIVE_AGENT_CATEGORY and t.source_opportunity_id is None and t.status in OPEN_STATUSES
    }
    return [
        Task(
            goal_id=goal_id,
            description="Draft a creative brief for the approved campaign",
            category=CREATIVE_AGENT_CATEGORY,
            reversible=True,
        )
        for goal_id in needs_brief_goal_ids - open_nudge_goal_ids
    ]
