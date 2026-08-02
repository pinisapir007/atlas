from atlas.brain.confidence import CATEGORY_TASK_CATEGORIES, confidence_score, goals_touching_category
from atlas.brain.explain import explain_opportunity
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Decision

# "Every recommendation must be based on real evidence collected from
# multiple independent sources" — a Decision Engine policy threshold (a
# stated methodology choice, the same class of transparent assumption as
# confidence.WEIGHTS), not a fact Intelligence reports. This constant lived
# in intelligence_advance.py before the Intelligence/Decision split; moved
# here because deciding "is this enough evidence to invest" is a decision,
# not a discovery.
MIN_INDEPENDENT_SOURCES = 2

# Absolute confidence delta below which a fresh decide() result isn't worth
# logging as a new Decision — the same anti-thrash discipline Strategist
# already applies to reallocation (only log when the outcome would actually
# differ). Without this, recency_score's continuous, tiny per-second decay
# would make every single tick "different" from the last, spamming a new
# Decision record every 30 minutes with no real evidence change behind it.
MATERIALITY_THRESHOLD = 0.02


def decide(category: str, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> Decision:
    """The Decision Engine's core function — the only place in this
    codebase allowed to turn evidence into a business verdict (standing
    architecture, locked 2026-08-02). Combines Intelligence's context-free
    confidence_score() with company context confidence_score() never
    sees — existing commitments, real execution capability — to decide
    whether this category is worth investing in.

    Pure and stateless: recomputes fresh from current KnowledgeBase/memory/
    kpis every call. This is what makes "nothing is permanently true"
    honest rather than cached — calling decide() again after new evidence
    arrives is the entire reopening mechanism; there's no stored verdict
    inside this function to go stale.

    Never touches the governance boundary: "propose_capability" concludes a
    new execution channel would be worth building, but only ever produces
    the same create_asset Task the existing, unmodified structural-proposal
    path already requires founder approval for. This function never
    creates an asset itself (scope clause locked 2026-08-02).

    Resource/capacity context is deliberately limited to what's genuinely
    knowable today — existing goals/tasks already touching this category.
    There is no real capital/budget model anywhere in this codebase; naming
    a fabricated one here would violate the same "never fabricate" rule
    every other factor in this system already respects, so this stays
    honestly narrow rather than falsely sophisticated.
    """
    result = confidence_score(category, knowledge, memory, kpis)
    sourced = [f for f in knowledge.findings() if f.category == category and f.evidence]
    channel = CATEGORY_TASK_CATEGORIES.get(category)
    existing_goals = goals_touching_category(category, memory)
    # goals_touching_category() can never catch a channel-less category (it
    # structurally has no real Task category to look for), so a capability
    # gap needs its own dedup signal or propose_capability would fire every
    # single call — engine_id is the same correlation key intelligence_advance
    # used before this split, preserved here since decide() is now the only
    # place that determines whether a capability gap was already flagged.
    already_proposed = any(g.engine_id == f"intelligence_{category}" for g in memory.goals())

    context = {
        "channel_ready": bool(channel),
        "already_pursuing": bool(existing_goals) or already_proposed,
        "existing_goal_ids": [g.id for g in existing_goals],
        "independent_sources": len(sourced),
    }
    risks = explain_opportunity(category, knowledge, memory, kpis)["risks"]

    if len(sourced) < MIN_INDEPENDENT_SOURCES:
        verdict = "insufficient_evidence"
        reasoning = (
            f"only {len(sourced)}/{MIN_INDEPENDENT_SOURCES} independently-sourced findings for '{category}' "
            "— standing policy requires multiple independent sources before any investment decision, "
            "regardless of confidence score"
        )
    elif existing_goals:
        verdict = "already_invested"
        reasoning = (
            f"'{category}' is already pursued by {len(existing_goals)} existing goal(s) "
            f"({', '.join(g.id for g in existing_goals)}) — no new commitment needed"
        )
    elif already_proposed:
        verdict = "already_proposed"
        reasoning = (
            f"a capability-gap proposal for '{category}' already exists — awaiting founder decision, "
            "not re-proposing"
        )
    elif not channel:  # None (unknown category) or set() (known category, no real channel yet) both mean no capability
        verdict = "propose_capability"
        reasoning = (
            f"'{category}' has {len(sourced)} independently-sourced findings but no dispatchable execution "
            "channel exists — proposing capability, never auto-creating one (standing rule, unchanged)"
        )
    else:
        confidence_note = (
            f"confidence {result['score']:.3f} ({result['factors_available']}/{result['factors_total']} evidence factors)"
            if result["score"] is not None
            else "confidence unscored"
        )
        verdict = "invest"
        reasoning = (
            f"'{category}' has {len(sourced)} independently-sourced findings, a real execution channel, "
            f"and no existing commitment — {confidence_note}"
        )

    return Decision(
        category=category,
        verdict=verdict,
        confidence=result["score"],
        factors=result["factors"],
        evidence_finding_ids=[f.id for f in sourced],
        context=context,
        risks=risks,
        reasoning=reasoning,
    )


def has_materially_changed(previous: Decision, new: Decision) -> bool:
    """Whether a fresh decide() result differs enough from the last
    recorded Decision for the same category to be worth logging as a new
    one — a verdict change is always material; a confidence change only
    counts once it clears MATERIALITY_THRESHOLD, so continuous evidence-
    freshness decay between ticks doesn't spam a new Decision every cycle."""
    if previous.verdict != new.verdict:
        return True
    if previous.confidence is None and new.confidence is None:
        return False
    if previous.confidence is None or new.confidence is None:
        return True
    return abs(previous.confidence - new.confidence) >= MATERIALITY_THRESHOLD


def decide_all(knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> list[Decision]:
    """One fresh Decision per category with any sourced finding — every
    call recomputes from current state, covering every category
    Intelligence has evidence for, not only ones already committed to."""
    categories = sorted({f.category for f in knowledge.findings() if f.evidence})
    return [decide(category, knowledge, memory, kpis) for category in categories]
