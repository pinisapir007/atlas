from atlas.brain.confidence import BOOTSTRAP_TASK_CATEGORY, OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES
from atlas.brain.feature_flags import opportunity_discovery_v1_enabled
from atlas.brain.models import Decision, Goal, Task, now


def supersede_pending_capability_proposals(category: str, memory, reason: str) -> int:
    """Close stale category-level capability proposals without fabricating failure.

    Only the exact Decision-Engine capability proposal is eligible:
    engine_id == intelligence_<category>, Task.category == create_asset, and
    the exact category-level execution-channel wording produced below.
    Brand/influencer create_asset proposals are therefore never touched.

    The Goal is paused, the Task becomes superseded, and the Proposal becomes
    superseded. BrainMemory persists the triplet atomically. The operation is
    idempotent and creates no reminder/sentinel/manual cleanup tail.
    """
    engine_id = f"intelligence_{category}"
    expected_description = f"Evaluate building a real '{category}' execution channel"

    goals = {g.id: g for g in memory.goals()}
    tasks = {t.id: t for t in memory.tasks()}
    changed = 0

    for proposal in memory.proposals():
        if proposal.kind != "create_asset":
            continue
        if proposal.status not in ("pending_approval", "superseded"):
            continue

        task = tasks.get(proposal.task_id)
        if task is None:
            continue
        goal = goals.get(task.goal_id)
        if goal is None:
            continue

        if goal.engine_id != engine_id:
            continue
        if task.category != "create_asset":
            continue
        if task.description != expected_description:
            continue

        touched = False

        if task.status == "pending_approval":
            task.transition("superseded", reason)
            touched = True

        if proposal.status == "pending_approval":
            proposal.status = "superseded"
            proposal.resolved_at = now()
            touched = True

        if goal.status == "active":
            goal.status = "paused"
            touched = True

        if touched:
            memory.save_capability_supersession(goal, task, proposal)
            changed += 1

    return changed


def apply_decision(decision: Decision) -> tuple[Goal | None, Task | None]:
    """Executes exactly one Decision Engine verdict — the only place that
    turns an "invest"/"propose_capability" verdict into a real Goal/Task.
    This function never decides anything itself; deciding is
    decision_engine.decide()'s exclusive job (standing architecture,
    locked 2026-08-02). It only acts on what's already been decided, and
    sets `decision.goal_id` on the passed-in object before it's ever
    persisted, so the saved Decision record cites the Goal it actually
    produced.

    "insufficient_evidence" / "already_invested" / "already_proposed"
    produce nothing — decide() already recorded exactly why no action is
    needed; there's nothing left for this function to execute.

    propose_capability still only ever produces a create_asset Task —
    the same, unmodified, always-founder-approval-gated path every
    capability gap has always used. This function never creates an asset
    itself (scope clause locked 2026-08-02).
    """
    if decision.verdict not in ("invest", "propose_capability"):
        return None, None

    engine_id = f"intelligence_{decision.category}"
    sources = decision.context.get("independent_sources", len(decision.evidence_finding_ids))

    if decision.verdict == "invest":
        goal = Goal(
            description=(
                f"Pursue {decision.category} opportunities "
                f"(Decision Engine: {sources} independently-sourced findings)"
            ),
            engine_id=engine_id,
        )
        bootstrap_category = BOOTSTRAP_TASK_CATEGORY[decision.category]
        if opportunity_discovery_v1_enabled() and decision.category in OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES:
            bootstrap_category = OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES[decision.category]
        task = Task(
            goal_id=goal.id,
            description=f"Bootstrap {decision.category} pipeline from Intelligence findings",
            category=bootstrap_category,
            reversible=True,
        )
    else:  # propose_capability
        goal = Goal(
            description=(
                f"Capability gap: no execution channel exists for '{decision.category}' "
                f"({sources} independently-sourced findings)"
            ),
            engine_id=engine_id,
        )
        task = Task(
            goal_id=goal.id,
            description=f"Evaluate building a real '{decision.category}' execution channel",
            category="create_asset",
        )

    decision.goal_id = goal.id
    return goal, task
