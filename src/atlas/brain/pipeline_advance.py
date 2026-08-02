from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

RECRUITMENT_ASSET_ID = "recruitment_workforce"
RECRUITMENT_CATEGORY = "revenue_recruitment_leads"

# Stages RecruitmentAgent advances on its own — deliberately excludes
# "proposal_ready"/"active" (founder-approval gates: approve_outreach /
# approve_commitment) and "won"/"lost" (terminal). The loop stops the moment
# an opportunity leaves this set — no separate gate-detection logic needed.
AUTO_ADVANCE_STAGES = {"discovered", "qualified", "matched"}


def advance_recruitment_pipeline(tasks: list[Task], registry: Registry, memory) -> list[Task]:
    """Recruitment-specific continuation: for every in-progress, goal-tagged
    opportunity, ensures exactly one open task exists to drive its next
    stage — never more than one, never for an opportunity that has reached a
    founder-approval gate or a terminal stage, never for an opportunity with
    no goal_id to attribute it to.

    Deliberately narrow — this is not a generic "keep every asset's pipeline
    moving" framework, just the one Recruitment-shaped bridge that was
    designed and approved.
    """
    try:
        report = registry.dispatch(RECRUITMENT_ASSET_ID, "report")
    except (UnsupportedVerb, KeyError):
        return []
    if not isinstance(report, dict):
        return []

    opportunities = report.get("opportunities")
    if not isinstance(opportunities, list):
        return []

    known_goal_ids = {g.id for g in memory.goals()}
    open_source_ids = {
        t.source_opportunity_id
        for t in tasks
        if t.source_opportunity_id is not None and t.status in OPEN_STATUSES
    }

    new_tasks: list[Task] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict):
            continue
        if opportunity.get("stage") not in AUTO_ADVANCE_STAGES:
            continue
        goal_id = opportunity.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue  # no goal to attribute a continuation task to, or not tracked by this brain — never fall back
        opportunity_id = opportunity.get("id")
        if not opportunity_id or opportunity_id in open_source_ids:
            continue  # a continuation task for this opportunity is already open

        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=f"Continue recruitment opportunity {opportunity_id} (currently {opportunity['stage']})",
                category=RECRUITMENT_CATEGORY,
                reversible=True,
                source_opportunity_id=opportunity_id,
            )
        )

    return new_tasks
