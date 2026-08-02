from atlas.brain.models import Decision, Goal, Task

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
        task = Task(
            goal_id=goal.id,
            description=f"Bootstrap {decision.category} pipeline from Intelligence findings",
            category=_BOOTSTRAP_TASK_CATEGORY[decision.category],
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
