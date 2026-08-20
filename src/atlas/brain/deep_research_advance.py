"""Shallow -> Deep Research Escalation Bridge (P0 Independence Mission,
2026-08-18). The real, verified gap this closes: research_request.py's
research_exhausted() already detects when shallow research has been
tried MAX_RESEARCH_ATTEMPTS times for a category with no result -- but
nothing before this ever acted on that fact. A category reaching that
state simply stayed stuck forever, needing an interactive session to
dig deeper by hand. This is the missing "what happens next" step,
following the exact same *_advance.py bridge shape every other one in
this codebase already uses (a plain function called from CEOBrain.
tick(), reading real state, creating real, deduplicated Tasks, no new
judgment invented here beyond "exhausted-but-still-unexplored -> try
deeper").

Gated on the identical feature_flags.executive_discovery_enabled()
flag Executive Discovery itself already uses (unset by default) -- not
a new switch: deep research is a real continuation of shallow research
(it only ever escalates a category shallow research already touched),
so it inherits the exact same Dev/Production separation rather than
becoming live in real production a moment before the founder has
approved Executive Discovery itself being live. Reuses discovery.
decide.discovery_goal() (the same standing "Executive Discovery" Goal
shallow research tasks already file under) rather than inventing a
second Goal -- renamed from _discovery_goal (2026-08-18, mechanical,
zero behavior change) specifically so this module could share it.

Marked reversible=True, identical risk posture to the shallow Research
Trigger it escalates from: real, read-only browsing plus real
KnowledgeBase writes, no financial/access/legal component, no
RiskPolicy change needed.
"""

from atlas.brain.discovery.deep_research_request import (
    DEEP_RESEARCH_TASK_CATEGORY,
    DEEP_RESEARCH_TASK_PREFIX,
    deep_research_task_description,
)
from atlas.brain.discovery.decide import discovery_goal
from atlas.brain.discovery.exploration_gate import unexplored_categories
from atlas.brain.discovery.research_request import research_exhausted
from atlas.brain.feature_flags import executive_discovery_enabled
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task


def categories_needing_deep_research(knowledge: KnowledgeBase, kpis: KPIRegistry) -> list[str]:
    """Every taxonomy category that's still unexplored (below decide()'s
    evidence bar) AND has already exhausted its real shallow research
    attempts -- exactly the categories the shallow Research Trigger can
    no longer help, sorted for deterministic output."""
    return [category for category in unexplored_categories(knowledge) if research_exhausted(category, kpis)]


def advance_deep_research(memory: BrainMemory, knowledge: KnowledgeBase, kpis: KPIRegistry) -> list[Task]:
    """Creates exactly one real, auto-delegating deep_research Task per
    category that has exhausted shallow research but still lacks
    evidence, skipping any category that already has an open (not yet
    done/failed/blocked) deep-research Task -- the same dedup discipline
    research_request.create_research_tasks() already applies via its own
    correlation key (the fixed description format itself). No-op with
    ATLAS_EXECUTIVE_DISCOVERY_ENABLED unset (default), the same
    inertness advance_executive_discovery() already has."""
    if not executive_discovery_enabled():
        return []

    needing = categories_needing_deep_research(knowledge, kpis)
    if not needing:
        return []

    open_categories = {
        task.description[len(DEEP_RESEARCH_TASK_PREFIX):]
        for task in memory.tasks()
        if task.category == DEEP_RESEARCH_TASK_CATEGORY
        and task.status not in ("done", "failed", "blocked")
        and task.description.startswith(DEEP_RESEARCH_TASK_PREFIX)
    }
    goal = discovery_goal(memory)
    created = []
    for category in needing:
        if category in open_categories:
            continue
        task = Task(
            goal_id=goal.id,
            description=deep_research_task_description(category),
            category=DEEP_RESEARCH_TASK_CATEGORY,
            reversible=True,
        )
        memory.save_task(task)
        created.append(task)
    return created
