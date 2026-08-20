"""Bridge 3: Reasoning -> Decision (2026-08-11, docs/
DESIGN_BRIDGE_3_REASONING_TO_DECISION.md) -- the last of the three
Connectivity Bridges. A Connectivity Bridge, not a Capability: adds zero
new judgment. Given real (Decision, Task) pairs that decision_engine.
decide()/decision_apply.apply_decision() ALREADY produced, unmodified,
and Bridge 2's real comparison results, it only adjusts the real,
existing `Task.priority_score` field for whichever category Reasoning
preferred -- reusing ceo.tick()'s own existing `open_tasks.sort(key=...
priority_score...)` mechanism to make that preference observable in real
delegation order.

Chosen mechanism, not assumed: a real, isolated experiment (see docs/
DESIGN_BRIDGE_3_REASONING_TO_DECISION.md, "Influence must be observable")
proved that reordering decide_all_with_discovery()'s own iteration has
ZERO observable effect in the current system (Task.priority_score is set
by a separate, later SimplePrioritizer pass inside tick(), never inside
decision-application itself) -- influencing priority_score directly is
the one mechanism with a real, already-existing, already-tested causal
path to an observable outcome. This is the best explanation standing
against real evidence, not proven true for all time (Principle of Honest
Evaluation) -- if a future Qualification Run finds it insufficient, this
gets revisited on new evidence, the same as every other locked decision
in this codebase.

Explicit non-goals, per the locked Design doc: never calls decide()/
decide_with_discovery()/apply_decision() itself; never creates Goal/Task/
Proposal; never changes a Decision's verdict, confidence, or any other
field; never skips a category -- every (Decision, Task) pair passed in
is still returned untouched unless it was Reasoning-preferred, and even
then only its priority_score changes.
"""

from atlas.brain.models import Decision, Opportunity, Task

# Same "stated, editable assumption" class as every other named constant
# in this codebase (confidence.WEIGHTS, reasoning.REASONING_WEIGHTS) --
# added on top of whatever SimplePrioritizer already computed, never
# replacing it.
REASONING_PRIORITY_BOOST = 1.0


def apply_reasoning_priority(
    decisions_and_tasks: list[tuple[Decision, Task | None]],
    comparisons: list[dict],
    opportunities_by_id: dict[str, Opportunity],
) -> list[Task]:
    """The real bridge entry point. `decisions_and_tasks` -- real
    (Decision, Task) pairs already produced by the unmodified decide()/
    apply_decision() flow (Task is None for verdicts that create nothing,
    e.g. "already_invested"). `comparisons` -- real results from Bridge 2
    (advance_opportunity_comparisons()). `opportunities_by_id` -- real
    Opportunities keyed by id, to map a comparison's `preferred_id` back
    to the real business category decide() actually used.

    Returns the real Tasks whose priority_score was boosted -- every
    other (Decision, Task) pair is returned to the caller completely
    unmodified, in the same object identity, never re-created."""
    preferred_categories = {
        opportunities_by_id[comparison["preferred_id"]].category
        for comparison in comparisons
        if comparison["preferred_id"] in opportunities_by_id
    }

    boosted = []
    for decision, task in decisions_and_tasks:
        if task is None:
            continue
        if decision.category in preferred_categories:
            task.priority_score += REASONING_PRIORITY_BOOST
            boosted.append(task)
    return boosted
