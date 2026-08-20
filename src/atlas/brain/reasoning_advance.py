"""Bridge 2: Opportunity -> Reasoning (2026-08-11, docs/
DESIGN_BRIDGE_2_OPPORTUNITY_TO_REASONING.md). A Connectivity Bridge, not a
Capability -- adds zero new judgment. It only groups real Opportunities by
their real, current stage and, for every group of 2+, invokes the
already-proven compare_opportunities() (brain/reasoning.py) unmodified.
Deleting this module leaves OpportunityStore and compare_opportunities()
each fully intact and independently working -- proof it holds no
capability of its own.

Stateless by design (feedback_bridge_design_principles): tracks no
"already compared" memory of its own, recomputes fresh from
OpportunityStore's real current state on every call. Safe to do -- unlike
Bridge 1, this bridge never writes anything, so there is no redundant-write
cost to avoid by remembering past calls. Calling this ten times on
unchanged real data returns the exact same real result every time.

Explicit non-goals, per the locked Design doc: never creates Goal/Task/
Proposal; never calls decide(); never touches Opportunity itself
(compare_opportunities() is already read-only); never compares across
different real stages (grouping already prevents this); never persists a
new durable record -- returns a real, computed result only.
"""

from atlas.brain.models import Opportunity
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.reasoning import compare_opportunities


def advance_opportunity_comparisons(opportunities: OpportunityStore) -> list[dict]:
    """The real bridge entry point -- groups every real Opportunity by its
    real current stage, and for each group of 2 or more, returns one real
    comparison result from compare_opportunities() (an N-way comparison
    across the whole group, never decomposed into pairs). A stage with
    only one real Opportunity is skipped silently, not an error -- there
    is nothing real to compare it against yet."""
    by_stage: dict[str, list[Opportunity]] = {}
    for opportunity in opportunities.opportunities():
        by_stage.setdefault(opportunity.stage, []).append(opportunity)

    results = []
    for stage, group in by_stage.items():
        if len(group) < 2:
            continue
        results.append(compare_opportunities(group))
    return results
