from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.asset_value import brand_lifetime_value, influencer_lifetime_value
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brand.factory import TASK_MARKER as BRAND_TASK_MARKER
from atlas.brand.factory import draft_brand_proposal, suggest_brand
from atlas.brand.models import Brand
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry, create_campaign, link_brand, set_status
from atlas.influencer.factory import TASK_MARKER as INFLUENCER_TASK_MARKER
from atlas.influencer.factory import draft_influencer_proposal, suggest_persona
from atlas.influencer.performance import performance_snapshot
from atlas.influencer.ranking import prefer_market_match, rank_influencers
from atlas.influencer.registry import InfluencerRegistry, add_category
from atlas.brain.opportunity_ranking import relevant_success_laws
from atlas.brain.success_patterns import best_pattern_for_category
from atlas.orchestrator.orchestrator import start_execution
from atlas.orchestrator.registry import ExecutionPlanRegistry

_ENGINE_ID_PREFIX = "intelligence_"
_SELECTED_STAGE = "selected_for_marketing"

# The founder's explicit choice (2026-08-03) for what happens when
# Opportunity Discovery V1 recommends a market with no matching Digital
# Influencer: reuse the existing, always-approval-gated create_asset
# structural-proposal path (Delegator._propose(), the same mechanism every
# other capability gap in this codebase already uses — see decide()'s
# "propose_capability" verdict) — never auto-generate an identity (every
# Digital Influencer stays founder-authored, no fabrication). Non-blocking,
# the same way propose_capability never blocks the rest of the system: the
# campaign still proceeds with the best real influencer available today.
_CAPABILITY_GAP_TASK_CATEGORY = "create_asset"

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
    brands: BrandRegistry | None = None,
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
    brands = brands if brands is not None else BrandRegistry()
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
            # No influencer is tagged for this category at all -- before
            # giving up, check whether a real, already-proven influencer
            # from a DIFFERENT category could be reused here instead of
            # requiring a brand new one (the founder's explicit directive,
            # 2026-08-03: "Digital Influencers are... long-term business
            # assets... the objective is not to create more influencers").
            reused = _find_reusable_influencer(opportunity.recommended_market, influencers, campaigns, memory, kpis)
            if reused is None:
                continue  # no influencer registered for this category, and no reusable match either
            add_category(reused["influencer_id"], category, influencers)
            ranked = [reused]
        # Prefers a real language match for opportunity.recommended_market
        # (2026-08-03, Opportunity Discovery V1) when one exists among the
        # already-ranked candidates; falls back to ranked[0] exactly like
        # before otherwise -- a pure extension, not a behavior change, for
        # every opportunity with no market recommendation (every founder-
        # manual intake today).
        chosen = prefer_market_match(ranked, opportunity.recommended_market, influencers)
        gap_task = _missing_market_influencer_task(opportunity, chosen, influencers, memory.tasks(), knowledge)
        if gap_task is not None:
            memory.save_task(gap_task)

        # Decision Engine Integration (2026-08-03): "Update Success Laws.
        # Improve the next decision." Records which real Success Laws were
        # relevant/considered at the moment this campaign was created — an
        # honest ASSOCIATION, never a causal claim (the same "aggregate
        # real outcomes, never claim causation" discipline
        # historical_success_score() already applies). Once this
        # campaign's real profit is measured, asset_value.
        # success_law_lifetime_value() can attribute it to these laws'
        # real track record, which future rank_by_real_track_record()
        # calls use to prefer laws with a real, positive history — closing
        # the loop this directive asked for, without inventing causation.
        law_ids = [law.id for law in relevant_success_laws(category, knowledge)]

        # Learning V1 (2026-08-09): the real, concrete behavior-change
        # wiring for "identify success patterns" -- before this, a new
        # campaign's content_formats/platform_strategy were always left
        # empty here (no code anywhere set them). If real, measured
        # profit from at least MIN_CAMPAIGNS_FOR_PATTERN prior campaigns
        # in this category supports one particular combination, ATLAS now
        # starts the new campaign with that real, evidence-backed
        # combination instead of nothing -- genuinely using accumulated
        # experience to change what it does next, not just recording it.
        # None (today's exact prior behavior) when there isn't enough
        # real evidence yet -- never guessed.
        pattern = best_pattern_for_category(category, campaigns, memory, kpis)

        campaign = create_campaign(
            business_objective=goal.description,
            category=category,
            product_offer=opportunity.product_name,
            influencer_ids=[chosen["influencer_id"]],
            influencer_registry=influencers,
            knowledge=knowledge,
            memory=memory,
            kpis=kpis,
            registry=campaigns,
            content_formats=pattern.content_formats if pattern else None,
            platform_strategy=pattern.platform_strategy if pattern else "",
            goal_id=goal.id,
            # The real, already-validated affiliate link (see
            # affiliate_department.models.validate_provider_link(), run at
            # real product intake) — without this, the campaign's CTA/
            # landing-page content would have nothing real to point at.
            destination_url=opportunity.real_affiliate_link,
            success_law_ids=law_ids,
        )
        set_status(campaign.id, "active", campaigns)
        start_execution(campaign.id, campaigns, execution_plans)

        # Business Asset Portfolio directive (2026-08-03): "Before creating
        # any new asset, ATLAS should first search for an existing
        # reusable asset that already fits the opportunity. If one
        # exists, reuse it." A Brand's identity is tied to a specific
        # product/niche, so the real reuse key is an exact niche match —
        # the same real product launching into a new market can reuse its
        # existing brand rather than getting a redundant duplicate.
        niche = opportunity.marketing_niche or opportunity.product_name
        reused_brand = _find_reusable_brand(niche, brands, campaigns, memory, kpis)
        if reused_brand is not None:
            link_brand(campaign.id, reused_brand.id, campaigns)
        else:
            # No existing brand fits -- propose creating one, unconditionally
            # for every real opportunity that reaches a Campaign, unlike the
            # influencer gap above (only raised on a market mismatch): the
            # founder's stated loop treats "create the brand" as a normal
            # step, not a fallback. Non-blocking, same as the influencer gap
            # -- the Campaign is already created and active regardless.
            brand_task = _missing_brand_task(opportunity, memory.tasks(), knowledge)
            if brand_task is not None:
                memory.save_task(brand_task)


def _decision_engine_category(goal) -> str | None:
    if goal.engine_id and goal.engine_id.startswith(_ENGINE_ID_PREFIX):
        return goal.engine_id[len(_ENGINE_ID_PREFIX):]
    return None


def _selected_opportunity_for_goal(goal_id: str, opportunities: list):
    matches = [o for o in opportunities if o.goal_id == goal_id and o.stage == _SELECTED_STAGE]
    return matches[0] if matches else None


def _find_reusable_influencer(
    market: str, influencers: InfluencerRegistry, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry
) -> dict | None:
    """Searches every real, active influencer regardless of which business
    categories they're already tagged for — the founder's explicit
    architectural directive (2026-08-03): "Digital Influencers are not
    marketing assets. They are long-term business assets... The objective
    is not to create more influencers. The objective is to build valuable
    reusable digital assets." Only reached when rank_influencers() already
    found nobody tagged for the category at all — reuse across business
    models is always tried before the Digital Influencer Factory ever
    proposes a brand new one.

    Ranks real market matches (IdentityProfile.market, the raw code —
    not `nationality`, the human name; the two are distinct fields since
    a name can never equal a code) by measured lifetime value
    (asset_value.influencer_lifetime_value() — real profit across
    every campaign they've ever been part of, any category) first,
    falling back to raw evidence volume (performance_snapshot()'s
    factors_available, the same signal rank_influencers() itself uses)
    when no campaign has measured profit yet — an established,
    already-proven asset is preferred over an unproven one, the same
    "real measured outcomes outweigh everything else" discipline
    confidence.WEIGHTS already applies elsewhere. None when market is ""
    or no active influencer's market matches it — never guesses a fit,
    and never reuses an influencer for a market they aren't actually
    built for.
    """
    if not market:
        return None
    eligible = [inf for inf in influencers.influencers() if inf.status == "active" and inf.identity.market == market]
    if not eligible:
        return None

    def _rank_key(inf) -> tuple:
        ltv = influencer_lifetime_value(inf.id, campaigns, memory, kpis)
        snapshot = performance_snapshot(inf.id, kpis)
        return (ltv is not None, ltv or 0.0, snapshot["factors_available"])

    best = max(eligible, key=_rank_key)
    return performance_snapshot(best.id, kpis)


def _find_reusable_brand(
    niche: str, brands: BrandRegistry, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry
) -> Brand | None:
    """Searches every real Brand for one already built around the exact
    same niche/product — the founder's explicit Business Asset Portfolio
    directive (2026-08-03): "Before creating any new asset, ATLAS should
    first search for an existing reusable asset that already fits the
    opportunity. If one exists, reuse it." A Brand's identity is
    fundamentally tied to a specific product, unlike a Digital Influencer
    (who can plausibly serve many different niches) — so the real reuse
    key here is an exact niche match, not a market match: the same real
    product expanding into a new market should reuse its one real brand,
    not spawn a duplicate.

    Ranks matches by measured lifetime value (asset_value.
    brand_lifetime_value() — real profit across every campaign it's ever
    been linked to) when more than one real brand shares the niche
    (shouldn't normally happen, but never arbitrary when it does). None
    when `niche` is "" or no real brand was ever built for it — never
    guesses a fit.
    """
    if not niche:
        return None
    eligible = [b for b in brands.brands() if b.niche == niche]
    if not eligible:
        return None

    def _rank_key(b: Brand) -> tuple:
        ltv = brand_lifetime_value(b.id, campaigns, memory, kpis)
        return (ltv is not None, ltv or 0.0)

    return max(eligible, key=_rank_key)


def _missing_market_influencer_task(
    opportunity: AffiliateOpportunity, chosen: dict, influencers: InfluencerRegistry, existing_tasks: list[Task], knowledge: KnowledgeBase
) -> Task | None:
    """A real, founder-gated capability-gap Task when opportunity.
    recommended_market names a market and the influencer prefer_market_match()
    actually chose doesn't speak it — the founder's explicit choice
    (2026-08-03) for this exact gap. None when there's no real mismatch
    (recommended_market is "" — every founder-manual intake today — or the
    chosen influencer genuinely matches), or when a gap task already exists
    for this opportunity (dedup via Task.source_opportunity_id, the same
    correlation key affiliate_intelligence_advance._request_founder_choice()
    already uses for the same purpose — never repeats a request once made).

    Description embeds the real Digital Influencer Factory draft
    (influencer.factory.draft_influencer_proposal()) — market, niche,
    category, and cited evidence — so the founder sees a genuine, evidence-
    backed recommendation, not just a bare "something is missing" flag.
    `atlas influencer create-from-proposal` re-derives the same draft from
    this task once approved (see cli.py) — never persisted separately,
    always recomputed from the real opportunity so it can never go stale.
    """
    market = opportunity.recommended_market
    if not market:
        return None
    chosen_influencer = influencers.get_influencer(chosen["influencer_id"])
    if chosen_influencer.identity.market == market:
        return None
    if any(
        t.category == _CAPABILITY_GAP_TASK_CATEGORY and t.source_opportunity_id == opportunity.id and t.description.startswith(INFLUENCER_TASK_MARKER)
        for t in existing_tasks
    ):
        return None

    draft = draft_influencer_proposal(opportunity, knowledge)
    persona = suggest_persona(draft)
    evidence_note = f" Evidence: {', '.join(draft.evidence)}." if draft.evidence else ""
    locale_note = f" Nationality: {draft.nationality}. Native language: {draft.native_language}." if draft.nationality else ""
    persona_note = (
        f" AI-suggested starting point (not evidence -- edit freely): name='{persona.local_name}', "
        f"age_range='{persona.age_range}', personality='{persona.personality}', "
        f"communication_style='{persona.communication_style}', visual_style='{persona.visual_style}', "
        f"preferred_platforms={persona.preferred_platforms}."
    )

    return Task(
        goal_id=opportunity.goal_id,
        description=(
            f"{INFLUENCER_TASK_MARKER} recommend creating a new influencer for market='{draft.recommended_market}', "
            f"niche='{draft.recommended_niche}', category='{draft.recommended_category}'.{locale_note} "
            f"Audience: {draft.recommended_audience}. {draft.rationale}{evidence_note}{persona_note} "
            f"Proceeding with '{chosen_influencer.identity.name}' for now — approving this will let you create the "
            "real identity with 'atlas influencer create-from-proposal' (defaults to the suggestion above; "
            "override any field, it's yours to edit)."
        ),
        category=_CAPABILITY_GAP_TASK_CATEGORY,
        source_opportunity_id=opportunity.id,
    )


def _missing_brand_task(opportunity: AffiliateOpportunity, existing_tasks: list[Task], knowledge: KnowledgeBase) -> Task | None:
    """A real, founder-gated Brand Factory proposal for every real
    opportunity that reaches a Campaign — unlike _missing_market_influencer_task
    (only raised on a market mismatch), a Brand is proposed
    unconditionally: the founder's stated end-to-end loop treats "create
    the brand" as a normal step immediately after persona creation, not a
    fallback for a gap. None only when a Brand proposal already exists for
    this opportunity (dedup via TASK_MARKER + Task.source_opportunity_id —
    the marker matters here since an Influencer Factory proposal can share
    the same category and source_opportunity_id).

    Description embeds the real Brand Factory draft (brand.factory.
    draft_brand_proposal()) — name/niche/category/market and cited
    evidence — the same "show the real recommendation, not a bare flag"
    treatment the influencer gap task already gets. `atlas brand
    create-from-proposal` re-derives the same draft from this task once
    approved — never persisted separately.
    """
    if any(
        t.category == _CAPABILITY_GAP_TASK_CATEGORY and t.source_opportunity_id == opportunity.id and t.description.startswith(BRAND_TASK_MARKER)
        for t in existing_tasks
    ):
        return None

    draft = draft_brand_proposal(opportunity, knowledge)
    suggestion = suggest_brand(draft)
    evidence_note = f" Evidence: {', '.join(draft.evidence)}." if draft.evidence else ""

    return Task(
        goal_id=opportunity.goal_id,
        description=(
            f"{BRAND_TASK_MARKER} recommend creating a new brand for niche='{draft.recommended_niche}', "
            f"category='{draft.recommended_category}', market='{draft.recommended_market or 'unspecified'}'. "
            f"{draft.rationale}{evidence_note} "
            f"AI-suggested starting point (not evidence -- edit freely): name='{draft.recommended_name}' "
            f"(the real product name), tagline='{suggestion.tagline}', visual_identity='{suggestion.visual_identity}', "
            f"voice='{suggestion.voice}'. Approving this will let you create the real brand with "
            "'atlas brand create-from-proposal' (defaults to the suggestion above; override any field)."
        ),
        category=_CAPABILITY_GAP_TASK_CATEGORY,
        source_opportunity_id=opportunity.id,
    )
