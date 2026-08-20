"""Revenue Strategy (Milestone 3, docs/DESIGN_REVENUE_STRATEGY.md, docs/
ARCHITECTURE_INTENT_REVENUE_STRATEGY.md, docs/
CAPABILITY_DEFINITION_REVENUE_STRATEGY.md -- all locked before this was
written) -- the real, missing bridge between a Subject already classified
"ready" (Milestone 2, opportunity_evaluation.evaluate_opportunities()) and
a real, Subject-attributed Goal with a chosen revenue model and a real
resource-aware commit/defer decision.

decision_apply.apply_decision()'s existing "invest" path is untouched --
it still creates one category-level Goal per category, knowing nothing
about any specific Subject. This module is the second, Subject-level
Goal-creation path the Architecture Intent named explicitly (not hidden):
the coordination between the two is resolved here, in Design section 3,
by joining an already-existing category Goal (via goals_touching_category(),
unchanged) rather than creating a duplicate, and by creating a new,
separate Goal only when the existing one is already claimed by another
Opportunity. This is Reuse Before Build applied to Goal creation itself,
not just to business assets.

Never mutates evaluate_opportunities()'s output, goals_touching_category(),
BOOTSTRAP_TASK_CATEGORIES, or decision_apply.py/decide() -- read-only
consumers of all of them, exactly as Architecture Intent's explicit
boundary section requires.

Reads BOOTSTRAP_TASK_CATEGORIES (plural, list-shaped -- 2026-08-12,
Milestone 3 Vision Milestone Review), not the older scalar
BOOTSTRAP_TASK_CATEGORY that decision_apply.py still uses untouched. Every
category has exactly one real channel in that list today (no fabricated
second option), read honestly as channels[0] -- but the shape itself no
longer forecloses a real second channel existing later, per the standing
Shape-vs-Implementation law in docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md §2.
"""

from atlas.brain.confidence import BOOTSTRAP_TASK_CATEGORIES, goals_touching_category
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.opportunity_evaluation import evaluate_opportunities

# Stated, editable policy constant -- same class as decision_engine.
# MIN_INDEPENDENT_SOURCES, opportunity_evaluation.EVALUATION_WEIGHTS: no
# real budget/capacity model exists anywhere in this codebase today
# (documented gap, Design section 1), so this MVP uses a simple, declared
# numeric threshold rather than inventing unearned sophistication. Counts
# real active Goals (BrainMemory.goals()), not a fabricated resource unit.
MAX_CONCURRENT_COMMITMENTS = 3


def _unclaimed_category_goal(category: str, memory: BrainMemory, opportunities: OpportunityStore) -> Goal | None:
    """The real category Goal (if any) that no other real Opportunity has
    already claimed via its own goal_id -- Design section 3, step 2."""
    existing = [g for g in goals_touching_category(category, memory) if g.status == "active"]
    if not existing:
        return None
    claimed_goal_ids = {o.goal_id for o in opportunities.by_category(category) if o.goal_id is not None}
    for goal in existing:
        if goal.id not in claimed_goal_ids:
            return goal
    return None


def commit_ready_opportunities(
    category: str, opportunities: OpportunityStore, knowledge: KnowledgeBase, memory: BrainMemory
) -> list[dict]:
    """The real Milestone 3 entry point. Reads Milestone 2's "ready" list
    (already ranked, highest first) for `category` and, for each Subject
    in that order: skips it if already committed (opportunity.goal_id is
    not None -- the at-most-one-active-Goal-per-Opportunity rule, enforced
    here, not assumed); skips it if no real execution channel exists yet
    for this category (BOOTSTRAP_TASK_CATEGORIES has no entry, or an empty
    list -- the existing propose_capability path already covers that gap,
    not duplicated here); defers it if the real resource threshold is already
    exhausted; otherwise joins an existing, unclaimed category Goal or
    creates a new, Subject-attributed one.

    Recomputes fresh every call -- no cached state, mirrors decide()'s own
    "nothing is permanently true" discipline. Never mutates
    evaluate_opportunities()'s output."""
    evaluation = evaluate_opportunities(category, opportunities, knowledge)
    active_count = len([g for g in memory.goals() if g.status == "active"])

    results = []
    for candidate in evaluation["ready"]:
        opportunity = opportunities.get_opportunity(candidate["opportunity_id"])

        if opportunity.goal_id is not None:
            results.append(
                {
                    "opportunity_id": opportunity.id,
                    "subject": opportunity.subject,
                    "status": "already_committed",
                    "goal_id": opportunity.goal_id,
                    "revenue_model": None,
                    "reasoning": f"'{opportunity.subject}' already committed to Goal {opportunity.goal_id} -- at most one active Goal per Opportunity, not re-decided.",
                }
            )
            continue

        # Plural-shaped lookup (BOOTSTRAP_TASK_CATEGORIES: dict[str, list[str]]):
        # honestly mechanical today (channels[0], the only real entry for
        # every category) -- real selection logic among multiple real
        # channels is deliberately not built here, since none has real
        # evidence to act on yet (Shape-vs-Implementation law).
        real_channels = BOOTSTRAP_TASK_CATEGORIES.get(category) or []
        revenue_model = real_channels[0] if real_channels else None
        if revenue_model is None:
            results.append(
                {
                    "opportunity_id": opportunity.id,
                    "subject": opportunity.subject,
                    "status": "no_real_channel",
                    "goal_id": None,
                    "revenue_model": None,
                    "reasoning": f"'{opportunity.subject}' ({category}): no real execution channel exists yet -- capability gap, not this module's decision to fabricate one.",
                }
            )
            continue

        if active_count >= MAX_CONCURRENT_COMMITMENTS:
            results.append(
                {
                    "opportunity_id": opportunity.id,
                    "subject": opportunity.subject,
                    "status": "deferred_resources",
                    "goal_id": None,
                    "revenue_model": revenue_model,
                    "reasoning": f"'{opportunity.subject}' ({category}): ready and ranked, but {active_count} active Goal(s) already at the declared {MAX_CONCURRENT_COMMITMENTS}-commitment threshold -- deferred, not rejected.",
                }
            )
            continue

        existing_goal = _unclaimed_category_goal(category, memory, opportunities)
        if existing_goal is not None:
            opportunity.goal_id = existing_goal.id
            opportunities.save_opportunity(opportunity)
            results.append(
                {
                    "opportunity_id": opportunity.id,
                    "subject": opportunity.subject,
                    "status": "joined_existing_goal",
                    "goal_id": existing_goal.id,
                    "revenue_model": revenue_model,
                    "reasoning": f"'{opportunity.subject}' ({category}): joined existing, unclaimed Goal {existing_goal.id} -- reuse before build, not a duplicate.",
                }
            )
            continue

        goal = Goal(
            description=f"Pursue '{opportunity.subject}' ({category}) -- committed via Revenue Strategy",
            engine_id=f"intelligence_{category}",
        )
        memory.save_goal(goal)
        task = Task(
            goal_id=goal.id,
            description=f"Bootstrap {revenue_model} for '{opportunity.subject}'",
            category=revenue_model,
            reversible=True,
        )
        memory.save_task(task)
        opportunity.goal_id = goal.id
        opportunity.task_id = task.id
        opportunities.save_opportunity(opportunity)
        active_count += 1
        results.append(
            {
                "opportunity_id": opportunity.id,
                "subject": opportunity.subject,
                "status": "committed_new_goal",
                "goal_id": goal.id,
                "revenue_model": revenue_model,
                "reasoning": f"'{opportunity.subject}' ({category}): committed to new Goal {goal.id}, model {revenue_model} -- ranked by Milestone 2, room available under the {MAX_CONCURRENT_COMMITMENTS}-commitment threshold.",
            }
        )

    return results
