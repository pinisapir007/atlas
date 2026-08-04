from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.feature_flags import opportunity_discovery_v1_enabled
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunity_ranking import rank_opportunities

_ENGINE_ID_PREFIX = "intelligence_"

# Only "affiliate" has a real destination today — the affiliate_intelligence
# pipeline that campaign_advance.py's bridge can actually reach (see
# confidence.OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES). Mirrors
# campaign_advance.BRIDGED_CATEGORIES exactly, kept as its own small
# constant here rather than importing that module's private set, since
# extending either independently should never require touching the other.
BRIDGED_CATEGORIES = {"affiliate"}


def advance_opportunity_discovery(memory: BrainMemory, knowledge: KnowledgeBase, affiliate_store: AffiliateStore) -> None:
    """Turns real, evidence-backed opportunity rankings into real
    AffiliateOpportunity records at stage "ranked" — the same stage
    intake_real_product() lands a founder-supplied opportunity at, so the
    existing, unmodified affiliate_intelligence_advance._request_founder_choice()
    picks these up for free on the very next call, no changes needed there.

    Off by default (feature_flags.opportunity_discovery_v1_enabled()) —
    per the founder's explicit instruction (2026-08-03) to keep every new
    Opportunity Discovery capability disconnected from real production
    until explicitly approved, even while development continues. With the
    flag off, this function is a documented no-op; the real, currently-
    running production tick is completely unaffected by this module
    existing in the working tree.

    Never invents commission/conversion/competition/difficulty numbers —
    those stay 0.0 (founder-supplied later, the same real commercial terms
    intake_real_product() has always required) — evidence tells ATLAS
    *which niche* to recommend, never *what deal was signed*. Idempotent:
    never recreates an opportunity for a (category, subject) already
    surfaced, the same dedup discipline campaign_advance.py already uses
    for goal_id.
    """
    if not opportunity_discovery_v1_enabled():
        return

    existing_subjects = {(o.category, o.product_name) for o in affiliate_store.opportunities()}

    for goal in memory.goals():
        if goal.status != "active":
            continue
        category = _decision_engine_category(goal)
        if category not in BRIDGED_CATEGORIES:
            continue

        for result in rank_opportunities(category, knowledge):
            if result["independent_sources"] < MIN_INDEPENDENT_SOURCES:
                continue  # same evidence bar the Decision Engine itself enforces
            if (category, result["subject"]) in existing_subjects:
                continue  # already surfaced once -- never recreate/duplicate

            opportunity = AffiliateOpportunity(
                product_name=result["subject"],
                description=f"Discovered from real evidence for '{category}': {result['independent_sources']} independent source(s).",
                category=category,
                marketing_niche=result["subject"],
                recommended_market=result["recommended_market"],
                notes=(
                    f"Opportunity Discovery V1: confidence {result['score']:.3f} "
                    f"({result['factors_available']}/{result['factors_total']} evidence factors). "
                    "Real commercial terms (commission, tracking link) not yet known -- "
                    "founder must supply them before this can become publish-ready."
                ),
                score=result["score"] or 0.0,
                goal_id=goal.id,
            )
            opportunity.transition(
                "ranked",
                f"Opportunity Discovery V1: real evidence-based ranking, recommended market "
                f"'{result['recommended_market'] or 'unspecified'}'",
            )
            affiliate_store.save_opportunity(opportunity)
            existing_subjects.add((category, result["subject"]))


def _decision_engine_category(goal) -> str | None:
    if goal.engine_id and goal.engine_id.startswith(_ENGINE_ID_PREFIX):
        return goal.engine_id[len(_ENGINE_ID_PREFIX):]
    return None
