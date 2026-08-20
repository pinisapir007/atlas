"""Executive Discovery's wrapper around decision_engine.decide()/
decide_all() (Milestone 1, docs/EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md) --
Alternative 2, chosen and locked in docs/
EXECUTIVE_DISCOVERY_PLACEMENT_DECISION.md: decision_engine.py and
decision_apply.py are never edited. This module wraps decide(): checks
Exploration Before Commitment first (Mechanism 1) and short-circuits to
a real "exploration_incomplete" verdict, without even calling the real
decide(), if breadth isn't met yet. Otherwise it defers entirely to the
real, unmodified decide() -- only re-labeling its own
"insufficient_evidence" into "insufficient_evidence_after_research"
(Mechanism 3) once that specific category's real research attempts are
exhausted, an honest, visible, different verdict from "we haven't looked
yet," never a silent repeat.

This is a real, working hypothesis, not permanent dogma (see the
placement decision doc's closing principle) -- if wrapping proves to
create real friction against the live system, we stop, re-review, and
change course on real evidence, not preference.
"""

from atlas.brain.decision_engine import decide as decide_engine
from atlas.brain.discovery.exploration_gate import explored_categories, unexplored_categories
from atlas.brain.discovery.research_request import (
    categories_needing_research,
    create_research_tasks,
    research_exhausted,
)
from atlas.brain.discovery.taxonomy import MIN_CATEGORIES_EXPLORED
from atlas.brain.feature_flags import executive_discovery_enabled
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Decision, Goal, Task

# The correlation key (mirrors decision_apply.py's "intelligence_{category}"
# engine_id convention) for the one, standing Goal every real research Task
# this module dispatches belongs to -- Executive Discovery is a continuous
# capability, not a one-off project, so it gets one durable, reused Goal
# rather than a new one per research dispatch.
DISCOVERY_ENGINE_ID = "executive_discovery"


def decide_with_discovery(category: str, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> Decision:
    """The real entry point CEOBrain uses instead of decision_engine.decide()
    directly -- see module docstring. With ATLAS_EXECUTIVE_DISCOVERY_ENABLED
    unset (default), defers straight to the real, unmodified decide() --
    zero behavior change from before Executive Discovery existed (see
    feature_flags.executive_discovery_enabled() for why this gate exists)."""
    if not executive_discovery_enabled():
        return decide_engine(category, knowledge, memory, kpis)

    explored = explored_categories(knowledge)
    if len(explored) < MIN_CATEGORIES_EXPLORED:
        return Decision(
            category=category,
            verdict="exploration_incomplete",
            confidence=None,
            factors={},
            context={
                "explored_categories": sorted(explored),
                "unexplored_categories": unexplored_categories(knowledge),
            },
            reasoning=(
                f"Exploration Before Commitment: only {len(explored)}/{MIN_CATEGORIES_EXPLORED} business-model "
                f"categories independently evidenced so far -- Executive Decision will not commit to '{category}' "
                "or any other category until the wider field has been checked "
                "(docs/ATLAS_V1_FAILURE_ANALYSIS.md, Failure 1/2)"
            ),
        )

    decision = decide_engine(category, knowledge, memory, kpis)
    if decision.verdict == "insufficient_evidence" and research_exhausted(category, kpis):
        decision.verdict = "insufficient_evidence_after_research"
        decision.reasoning += (
            " -- Research Completion Threshold reached: real automated research was already attempted the "
            "maximum number of times for this category with no result clearing the evidence bar; this needs a "
            "founder decision, not more silent looking"
        )
    return decision


def decide_all_with_discovery(knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> list[Decision]:
    """The real drop-in replacement for decision_engine.decide_all() --
    same category selection, each routed through decide_with_discovery()
    instead of decide() directly."""
    categories = sorted({f.category for f in knowledge.findings() if f.evidence})
    return [decide_with_discovery(category, knowledge, memory, kpis) for category in categories]


def discovery_goal(memory: BrainMemory) -> Goal:
    existing = [g for g in memory.goals() if g.engine_id == DISCOVERY_ENGINE_ID]
    if existing:
        return existing[0]
    goal = Goal(
        description="Executive Discovery: continuously research the business-model landscape before ATLAS commits to any one",
        engine_id=DISCOVERY_ENGINE_ID,
        horizon="long",
    )
    memory.save_goal(goal)
    return goal


def advance_executive_discovery(knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> list[Task]:
    """The real CEOBrain.tick() bridge (same shape as every other
    *_advance.py bridge) -- for every category the breadth gate or a
    specific decide_with_discovery() call flagged as needing real
    evidence, dispatches real research via create_research_tasks(),
    under one standing "Executive Discovery" Goal (found or created
    once, reused every call). No-op with ATLAS_EXECUTIVE_DISCOVERY_ENABLED
    unset (default) -- see feature_flags.executive_discovery_enabled()."""
    if not executive_discovery_enabled():
        return []

    needing_research = categories_needing_research(knowledge, kpis)
    if not needing_research:
        return []
    goal = discovery_goal(memory)
    return create_research_tasks(goal.id, needing_research, memory, kpis)
