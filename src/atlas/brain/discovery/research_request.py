"""Research Trigger (Executive Discovery, Milestone 1, docs/
EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md, Mechanism 2) -- when Executive
Decision can't yet commit (a specific category is still below decide()'s
evidence bar, or the breadth gate flagged other unexplored taxonomy
categories), this creates a real, dispatchable Task instead of silently
waiting for a Finding to arrive -- closing the demand-driven-research gap
named in docs/ATLAS_V1_FAILURE_ANALYSIS.md (Failure 3).

Reuses Task/KPIRegistry/BrainMemory completely unmodified -- this module
only decides WHICH categories need research and creates the Task;
atlas.assets.research_discovery.agent.ResearchDiscoveryAgent (a real,
registered, Triggerable asset) is what Delegator's existing, unmodified
category-matching dispatches it to -- the same "a decision already made
elsewhere becomes a real, auto-delegating Task" shape
atlas.hands.dispatch.request_hands_action() already established.

The target category is carried in Task.description via one fixed,
code-owned format (RESEARCH_TASK_PREFIX) rather than a new persisted
entity -- proportionate to what a research request actually needs to
carry (one category string), unlike atlas.hands.models.HandsRequest (a
real multi-step action sequence -- genuine complexity a description
string can't hold). Created and parsed by exactly the two functions
below, never freeform text a human is expected to type by hand.
"""

from atlas.brain.discovery.exploration_gate import unexplored_categories
from atlas.brain.discovery.taxonomy import MAX_RESEARCH_ATTEMPTS
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task

RESEARCH_TASK_CATEGORY = "request_research"
RESEARCH_TASK_PREFIX = "Research business model category: "


def research_task_description(category: str) -> str:
    return f"{RESEARCH_TASK_PREFIX}{category}"


def category_from_research_task(task: Task) -> str:
    """The inverse of research_task_description() -- raises loudly if
    `task` isn't a real Research Trigger task rather than silently
    guessing, the same fail-closed discipline this codebase applies to
    every other structural assumption."""
    if not task.description.startswith(RESEARCH_TASK_PREFIX):
        raise ValueError(f"task {task.id!r} is not a real research-trigger task: {task.description!r}")
    return task.description[len(RESEARCH_TASK_PREFIX):]


def _attempts_kpi_name(category: str) -> str:
    return f"research_attempts_{category}"


def research_attempts(category: str, kpis: KPIRegistry) -> int:
    return int(kpis.latest(_attempts_kpi_name(category)) or 0)


def research_exhausted(category: str, kpis: KPIRegistry) -> bool:
    """True once MAX_RESEARCH_ATTEMPTS real research dispatches have
    already happened for `category` with no result clearing the evidence
    bar -- the Research Completion Threshold's stop signal (Mechanism 3),
    so the Research Trigger below never loops forever."""
    return research_attempts(category, kpis) >= MAX_RESEARCH_ATTEMPTS


def categories_needing_research(knowledge: KnowledgeBase, kpis: KPIRegistry) -> list[str]:
    """Every taxonomy category still below decide()'s evidence bar that
    hasn't exhausted its real research attempts yet. Unifies both real
    triggers -- a specific category decide() called "insufficient_
    evidence" on, and any other unexplored taxonomy category the breadth
    gate flagged -- into one mechanism, since both are the exact same
    real fact: this category doesn't have enough real evidence yet."""
    return [category for category in unexplored_categories(knowledge) if not research_exhausted(category, kpis)]


def create_research_tasks(
    goal_id: str, categories: list[str], memory: BrainMemory, kpis: KPIRegistry
) -> list[Task]:
    """Creates one real, auto-delegating Task per category still needing
    research, skipping any category that already has an open (not yet
    done/failed/blocked) research Task -- the same dedup discipline
    every other pipeline-advance bridge in this codebase already applies
    via a correlation key (here: the fixed description format itself).
    Marked reversible=True: real research is cheap, safe, and
    auto-delegates exactly like SimplePlanner's own generated tasks --
    no founder approval needed just to go look something up."""
    open_categories = {
        category_from_research_task(t)
        for t in memory.tasks()
        if t.category == RESEARCH_TASK_CATEGORY
        and t.status not in ("done", "failed", "blocked")
        and t.description.startswith(RESEARCH_TASK_PREFIX)
    }
    created = []
    for category in categories:
        if category in open_categories:
            continue
        task = Task(
            goal_id=goal_id,
            description=research_task_description(category),
            category=RESEARCH_TASK_CATEGORY,
            reversible=True,
        )
        memory.save_task(task)
        kpis.record(_attempts_kpi_name(category), research_attempts(category, kpis) + 1)
        created.append(task)
    return created
