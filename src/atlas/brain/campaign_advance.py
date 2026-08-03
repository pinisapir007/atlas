from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.campaign.registry import CampaignRegistry, create_campaign, set_status
from atlas.influencer.ranking import rank_influencers
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.orchestrator import start_execution
from atlas.orchestrator.registry import ExecutionPlanRegistry

_ENGINE_ID_PREFIX = "intelligence_"
_SELECTED_STAGE = "selected_for_marketing"

# Only "affiliate" has a real, non-fabricated product-selection signal
# today: AffiliateOpportunity.stage == "selected_for_marketing", reached
# only through the existing, unmodified founder flow (atlas affiliate
# product add -> affiliate_intelligence_advance's founder-choice Task ->
# approve()). "digital_product"/"content" have no such mechanism —
# their execution channels are still hardcoded placeholders (see
# confidence.PLACEHOLDER_TASK_CATEGORIES) with no real per-product data
# to select from at all. Extending this bridge to them requires a real
# product-selection mechanism to exist first for that category — not
# invented here, since there is no real evidence to build one from.
BRIDGED_CATEGORIES = {"affiliate"}


def advance_decision_driven_campaigns(
    memory: BrainMemory,
    knowledge: KnowledgeBase,
    kpis: KPIRegistry,
    influencers: InfluencerRegistry,
    campaigns: CampaignRegistry,
    execution_plans: ExecutionPlanRegistry,
    affiliate_store: AffiliateStore | None = None,
) -> None:
    """Bridges the Decision Engine's category-level "invest" verdict to a
    real, running Campaign — "the Decision Engine should... create the
    Campaign, assign the selected product, generate the complete content
    package, advance the workflow automatically through every internal
    ATLAS stage" (founder's framing, 2026-08-03, architecture locked).

    Reuses every existing mechanism unchanged, invents no new evidence-
    scoring: `Goal.engine_id` (decision_apply.py's existing
    "intelligence_{category}" correlation key) finds Decision-Engine-
    created goals; `AffiliateOpportunity.stage == "selected_for_marketing"`
    (the existing, founder-driven real product-choice signal) is the real
    product; `rank_influencers()` (built, previously unwired) is the real
    influencer choice; `create_campaign()`/`start_execution()` are
    unchanged. A goal only ever gets a Campaign once a human has already
    picked a real product for it through the existing, untouched approval
    flow — this function only automates everything after that real choice
    exists; it never invents which product or ranks products itself.

    Stops exactly at the standing governance boundary: the Campaign is
    created and activated (an internal, reversible, zero-cost workflow
    transition — the same class of action Strategist's own goal
    reallocation already applies directly, without RiskPolicy, since
    nothing real-world happens yet) and its execution is started and
    advanced as far as it can go automatically — which is up to
    `request_founder_review`, a real Task that RiskPolicy always routes
    to `pending_approval` (unreversible=False). Nothing past that point
    can ever happen without a human approving first; this function never
    weakens or bypasses that gate.

    Idempotent and safe to call every tick: a goal that already has a
    Campaign is skipped (`campaigns.campaigns()` is the dedup check, the
    same "check what already exists before creating" discipline
    `decide()`'s own `already_invested`/`already_proposed` verdicts use).
    A goal with no real selected product yet, or no influencer registered
    for its category yet, is simply left alone — re-evaluated fresh next
    tick, no special retry needed, the same resumability every other
    mechanism in this codebase already has.
    """
    # DEFAULT_STORE_PATH (".atlas/affiliate_intelligence.json") — not
    # affiliate_department.json's own default. "selected_for_marketing" is
    # only ever set by AffiliateIntelligenceAgent._mark_selected_for_marketing(),
    # which reads/writes the shared store file Affiliate Intelligence/
    # Content Factory/Editorial Review/Creative Agent/Publishing Gateway
    # all already use — the placeholder-discovery affiliate_department.json
    # chain (affiliate_pipeline_advance.py) never reaches this stage at all.
    affiliate_store = affiliate_store if affiliate_store is not None else AffiliateStore(DEFAULT_STORE_PATH)
    claimed_goal_ids = {c.goal_id for c in campaigns.campaigns() if c.goal_id}
    opportunities = affiliate_store.opportunities()

    for goal in memory.goals():
        if goal.status != "active":
            continue
        category = _decision_engine_category(goal)
        if category not in BRIDGED_CATEGORIES:
            continue
        if goal.id in claimed_goal_ids:
            continue

        opportunity = _selected_opportunity_for_goal(goal.id, opportunities)
        if opportunity is None:
            continue  # no real product chosen yet — wait for the founder

        ranked = rank_influencers(category, influencers, kpis)
        if not ranked:
            continue  # no influencer registered for this category yet

        campaign = create_campaign(
            business_objective=goal.description,
            category=category,
            product_offer=opportunity.product_name,
            influencer_ids=[ranked[0]["influencer_id"]],
            influencer_registry=influencers,
            knowledge=knowledge,
            memory=memory,
            kpis=kpis,
            registry=campaigns,
            goal_id=goal.id,
        )
        set_status(campaign.id, "active", campaigns)
        start_execution(campaign.id, campaigns, execution_plans)


def _decision_engine_category(goal) -> str | None:
    if goal.engine_id and goal.engine_id.startswith(_ENGINE_ID_PREFIX):
        return goal.engine_id[len(_ENGINE_ID_PREFIX):]
    return None


def _selected_opportunity_for_goal(goal_id: str, opportunities: list):
    matches = [o for o in opportunities if o.goal_id == goal_id and o.stage == _SELECTED_STAGE]
    return matches[0] if matches else None
