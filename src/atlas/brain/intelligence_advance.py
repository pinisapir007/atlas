from collections import defaultdict

from atlas.brain.confidence import goals_touching_category
from atlas.brain.kpi import KPIRegistry
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task

# "Every recommendation must be based on real evidence collected from
# multiple independent sources" (standing policy, 2026-08-02). A single
# finding, however well-sourced, is not "multiple independent sources" —
# this is the literal, structural gate, not a numeric confidence threshold.
# A confidence-score threshold was considered and rejected: the three
# highest-weighted factors (measured_outcomes, historical_success,
# internal_experiments) can only ever have data *after* something is
# pursued, so gating first-time promotion on them being present would make
# promotion permanently impossible — circular, not conservative.
MIN_INDEPENDENT_SOURCES = 2

# Which real, dispatchable Task category actually bootstraps each channel's
# existing pipeline — a channel-ready category gets exactly one such entry.
# Sourced from the same real manifest.toml categories as
# confidence.CATEGORY_TASK_CATEGORIES, not guessed.
_BOOTSTRAP_TASK_CATEGORY = {
    "affiliate": "affiliate_pipeline",
    "digital_product": "revenue_digital_product",
    "content": "revenue_content_assets",
    "recruitment": "revenue_recruitment_leads",
}


def advance_intelligence(
    knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry
) -> tuple[list[Goal], list[Task]]:
    """Converts a well-evidenced, not-yet-pursued category into a real
    execution plan: a Goal (engine_id-tagged as an Intelligence-originated
    internal experiment — the first real use of that dormant field) plus
    one bootstrap Task, using the same "one open task keeps a goal moving"
    principle SimplePlanner already applies. A category with no
    dispatchable channel gets a capability-gap Goal plus a create_asset
    Task instead — routes through the existing, unmodified
    structural-proposal path (create_asset is already
    ALWAYS_REQUIRES_APPROVAL), never an auto-created asset, per the
    standing "capability gaps produce a Proposal, not an asset" rule.

    Never promotes a category twice (tracked via Goal.engine_id) and never
    promotes a channel-ready category that a human (or an earlier tick)
    already created a goal for — checked via goals_touching_category(),
    the same real Task-category linkage confidence scoring already uses,
    not a separate tracking mechanism.
    """
    sourced_by_category: dict[str, list] = defaultdict(list)
    for finding in knowledge.findings():
        if finding.evidence:
            sourced_by_category[finding.category].append(finding)

    new_goals: list[Goal] = []
    new_tasks: list[Task] = []

    for category, sourced in sourced_by_category.items():
        if len(sourced) < MIN_INDEPENDENT_SOURCES:
            continue

        engine_id = f"intelligence_{category}"
        if any(g.engine_id == engine_id for g in memory.goals()):
            continue  # already promoted, by this bridge, previously

        bootstrap_category = _BOOTSTRAP_TASK_CATEGORY.get(category)
        if bootstrap_category is not None and goals_touching_category(category, memory):
            continue  # a real goal (human-created or already auto-promoted) already pursues this channel

        if bootstrap_category is None:
            goal = Goal(
                description=(
                    f"Capability gap: no execution channel exists for '{category}' "
                    f"({len(sourced)} independently-sourced findings)"
                ),
                engine_id=engine_id,
            )
            task = Task(
                goal_id=goal.id,
                description=f"Evaluate building a real '{category}' execution channel",
                category="create_asset",
            )
        else:
            goal = Goal(
                description=(
                    f"Pursue {category} opportunities "
                    f"(auto-promoted by Intelligence: {len(sourced)} independently-sourced findings)"
                ),
                engine_id=engine_id,
            )
            task = Task(
                goal_id=goal.id,
                description=f"Bootstrap {category} pipeline from Intelligence findings",
                category=bootstrap_category,
                reversible=True,
            )

        new_goals.append(goal)
        new_tasks.append(task)

    return new_goals, new_tasks
