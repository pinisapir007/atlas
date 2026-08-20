"""Exploration Before Commitment (Executive Discovery, Milestone 1,
docs/EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md, Mechanism 1) -- gates
Executive Decision from committing to ANY category until a real, minimum
breadth of the business-model taxonomy has been independently evidenced.

Deliberately global, not per-category: v1's failure was not "category X
had too little evidence" -- decision_engine.decide() already catches
that via MIN_INDEPENDENT_SOURCES -- it was "ATLAS never checked whether
a better category existed at all" (docs/ATLAS_V1_FAILURE_ANALYSIS.md,
Failure 1/2). This module answers a different question: has the wider
field been looked at, not just the one category currently being decided.

Reuses decision_engine.MIN_INDEPENDENT_SOURCES exactly -- the same
evidence bar decide() already applies per-category, never a second,
different number, so "explored" means precisely what decide() itself
would already consider sufficient for that one category.
"""

from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.discovery.taxonomy import BUSINESS_MODEL_CATEGORIES, MIN_CATEGORIES_EXPLORED
from atlas.brain.knowledge import KnowledgeBase


def sourced_finding_count(category: str, knowledge: KnowledgeBase) -> int:
    """Independently-sourced findings for `category` -- the identical
    real computation decide() itself performs (real Findings with a real
    evidence citation), kept in one place rather than reimplemented, so
    "explored" can never silently drift from what decide() actually
    requires."""
    return sum(1 for f in knowledge.findings(category=category) if f.evidence)


def explored_categories(knowledge: KnowledgeBase) -> set[str]:
    """Every taxonomy category that already clears decide()'s own
    evidence bar -- real, sourced findings, not a lower or different
    threshold invented here."""
    return {
        category
        for category in BUSINESS_MODEL_CATEGORIES
        if sourced_finding_count(category, knowledge) >= MIN_INDEPENDENT_SOURCES
    }


def unexplored_categories(knowledge: KnowledgeBase) -> list[str]:
    """Every taxonomy category still below decide()'s evidence bar --
    the real input to the Research Trigger
    (research_request.categories_needing_research()), sorted for
    deterministic output."""
    explored = explored_categories(knowledge)
    return sorted(category for category in BUSINESS_MODEL_CATEGORIES if category not in explored)


def exploration_sufficient(knowledge: KnowledgeBase) -> bool:
    """Whether Executive Decision is allowed to commit to any category
    yet -- MIN_CATEGORIES_EXPLORED distinct taxonomy categories must
    each independently clear the evidence bar first, not just the one
    category currently being decided."""
    return len(explored_categories(knowledge)) >= MIN_CATEGORIES_EXPLORED
