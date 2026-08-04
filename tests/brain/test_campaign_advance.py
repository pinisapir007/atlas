from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.campaign_advance import _missing_market_influencer_task, advance_decision_driven_campaigns
from atlas.brand.factory import TASK_MARKER as BRAND_TASK_MARKER
from atlas.influencer.factory import TASK_MARKER as INFLUENCER_TASK_MARKER
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.brand.models import Brand
from atlas.brand.registry import BrandRegistry
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry


class _World:
    def __init__(self, tmp_path):
        self.memory = BrainMemory(tmp_path / "brain.json")
        self.kpis = KPIRegistry(self.memory)
        self.knowledge = KnowledgeBase(tmp_path / "knowledge.json")
        self.influencers = InfluencerRegistry(tmp_path / "influencers.json")
        self.campaigns = CampaignRegistry(tmp_path / "campaigns.json")
        self.brands = BrandRegistry(tmp_path / "brands.json")
        self.execution_plans = ExecutionPlanRegistry(tmp_path / "execution_plans.json")
        self.affiliate_store = AffiliateStore(tmp_path / "affiliate_intelligence.json")

    def advance(self):
        advance_decision_driven_campaigns(
            self.memory, self.knowledge, self.kpis, self.influencers, self.campaigns, self.execution_plans,
            self.affiliate_store, self.brands,
        )

    def decision_engine_goal(self, category="affiliate", status="active") -> Goal:
        goal = Goal(description=f"Pursue {category} opportunities", engine_id=f"intelligence_{category}", status=status)
        self.memory.save_goal(goal)
        return goal

    def selected_opportunity(
        self, goal_id, product_name="KetoDNA", real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/", recommended_market=""
    ) -> AffiliateOpportunity:
        opportunity = AffiliateOpportunity(
            product_name=product_name, description="a real product", goal_id=goal_id, stage="selected_for_marketing",
            real_affiliate_link=real_affiliate_link, recommended_market=recommended_market,
        )
        self.affiliate_store.save_opportunity(opportunity)
        return opportunity

    def influencer(self, name="Mira", categories=("affiliate",), market="") -> DigitalInfluencer:
        influencer = DigitalInfluencer(identity=IdentityProfile(name=name, market=market), categories=list(categories))
        self.influencers.save_influencer(influencer)
        return influencer


def test_goal_without_engine_id_is_ignored(tmp_path):
    world = _World(tmp_path)
    goal = Goal(description="a manually-created goal, not Decision-Engine-driven")
    world.memory.save_goal(goal)
    world.selected_opportunity(goal.id)
    world.influencer()

    world.advance()

    assert world.campaigns.campaigns() == []


def test_goal_for_an_unbridged_category_is_ignored(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal(category="digital_product")
    world.influencer(categories=["digital_product"])
    # no real per-product selection mechanism exists for digital_product —
    # nothing to even attempt here, confirming the bridge doesn't reach in

    world.advance()

    assert world.campaigns.campaigns() == []


def test_goal_with_no_selected_product_yet_is_left_alone(tmp_path):
    world = _World(tmp_path)
    world.decision_engine_goal()
    world.influencer()
    # no AffiliateOpportunity created at all

    world.advance()

    assert world.campaigns.campaigns() == []


def test_goal_with_no_real_selected_stage_is_left_alone(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = AffiliateOpportunity(product_name="KetoDNA", description="d", goal_id=goal.id, stage="ranked")
    world.affiliate_store.save_opportunity(opportunity)
    world.influencer()

    world.advance()

    assert world.campaigns.campaigns() == []


def test_goal_with_a_real_product_but_no_influencer_is_left_alone(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id)
    # no influencer registered for "affiliate" at all

    world.advance()

    assert world.campaigns.campaigns() == []


def test_paused_goal_is_not_bridged(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal(status="paused")
    world.selected_opportunity(goal.id)
    world.influencer()

    world.advance()

    assert world.campaigns.campaigns() == []


def test_real_product_and_influencer_together_create_and_activate_a_campaign(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, product_name="KetoDNA")
    influencer = world.influencer()

    world.advance()

    campaigns = world.campaigns.campaigns()
    assert len(campaigns) == 1
    campaign = campaigns[0]
    assert campaign.goal_id == goal.id
    assert campaign.category == "affiliate"
    assert campaign.product_offer == "KetoDNA"
    assert campaign.influencer_ids == [influencer.id]
    assert campaign.status == "active"
    assert campaign.business_objective == goal.description
    # The real, already-validated affiliate link -- without this the
    # campaign's CTA/landing-page content would have nothing real to
    # point at (see orchestrator._produce_content()'s destination_url check).
    assert campaign.destination_url == "https://www.digistore24.com/redir/123456/myaffid/"


def test_campaign_links_real_relevant_success_laws_at_creation(tmp_path):
    from atlas.brain.models import SuccessLaw

    world = _World(tmp_path)
    matching = SuccessLaw(principle="p1", source_description="s", applicable_business_models=["affiliate"])
    unrelated = SuccessLaw(principle="p2", source_description="s", applicable_business_models=["content"])
    world.knowledge.save_success_law(matching)
    world.knowledge.save_success_law(unrelated)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, product_name="KetoDNA")
    world.influencer()

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    assert campaign.success_law_ids == [matching.id]


def test_campaign_has_no_success_law_ids_when_none_are_relevant(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, product_name="KetoDNA")
    world.influencer()

    world.advance()

    assert world.campaigns.campaigns()[0].success_law_ids == []


def test_a_real_campaign_also_raises_a_brand_factory_proposal(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = world.selected_opportunity(goal.id, product_name="KetoDNA")
    world.influencer()

    world.advance()

    brand_tasks = [
        t for t in world.memory.tasks()
        if t.category == "create_asset" and t.source_opportunity_id == opportunity.id and t.description.startswith(BRAND_TASK_MARKER)
    ]
    assert len(brand_tasks) == 1
    assert "KetoDNA" in brand_tasks[0].description


def test_brand_proposal_raised_even_with_no_market_recommendation(tmp_path):
    # Unlike the influencer gap (only on a market mismatch), a Brand is
    # proposed unconditionally -- confirms it fires for a plain,
    # founder-manual-style opportunity with recommended_market == "".
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = world.selected_opportunity(goal.id, recommended_market="")
    world.influencer()

    world.advance()

    brand_tasks = [
        t for t in world.memory.tasks()
        if t.category == "create_asset" and t.source_opportunity_id == opportunity.id and t.description.startswith(BRAND_TASK_MARKER)
    ]
    assert len(brand_tasks) == 1


def test_brand_proposal_never_duplicated_across_repeated_advances(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = world.selected_opportunity(goal.id)
    world.influencer()

    world.advance()
    world.advance()
    world.advance()

    brand_tasks = [
        t for t in world.memory.tasks()
        if t.category == "create_asset" and t.source_opportunity_id == opportunity.id and t.description.startswith(BRAND_TASK_MARKER)
    ]
    assert len(brand_tasks) == 1


def test_creating_a_campaign_also_starts_its_execution_plan(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id)
    world.influencer()

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    plans = world.execution_plans.plans_for_campaign(campaign.id)
    assert len(plans) == 1
    assert plans[0].status == "in_progress"


def test_advancing_twice_never_creates_a_second_campaign_for_the_same_goal(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id)
    world.influencer()

    world.advance()
    world.advance()
    world.advance()

    assert len(world.campaigns.campaigns()) == 1
    assert len(world.execution_plans.plans_for_campaign(world.campaigns.campaigns()[0].id)) == 1


def test_picks_the_top_ranked_influencer_when_multiple_are_eligible(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id)
    thin = world.influencer("Thin")
    rich = world.influencer("Rich")
    from atlas.influencer.performance import record_metric
    record_metric(rich.id, "followers", 10000.0, world.kpis)
    record_metric(rich.id, "views", 50000.0, world.kpis)

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    assert campaign.influencer_ids == [rich.id]


def test_prefers_a_market_matching_influencer_over_a_higher_ranked_non_match(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, recommended_market="US")
    rich_wrong_market = world.influencer("Rich", market="DE")
    thin_right_market = world.influencer("Thin", market="US")
    from atlas.influencer.performance import record_metric
    record_metric(rich_wrong_market.id, "followers", 10000.0, world.kpis)  # ranks higher on raw evidence

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    assert campaign.influencer_ids == [thin_right_market.id]


# --- _missing_market_influencer_task (isolated, unit-tested before ever
# being wired into advance_decision_driven_campaigns above) --------------


def _opp(recommended_market="", goal_id="goal-a", product_name="KetoDNA") -> AffiliateOpportunity:
    return AffiliateOpportunity(product_name=product_name, description="d", goal_id=goal_id, recommended_market=recommended_market)


def test_missing_market_influencer_task_is_none_when_no_market_was_recommended(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira", market="DE"), categories=["affiliate"])
    registry.save_influencer(influencer)

    task = _missing_market_influencer_task(_opp(recommended_market=""), {"influencer_id": influencer.id}, registry, [], KnowledgeBase(tmp_path / 'knowledge.json'))

    assert task is None


def test_missing_market_influencer_task_is_none_when_the_chosen_influencer_matches(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["affiliate"])
    registry.save_influencer(influencer)

    task = _missing_market_influencer_task(_opp(recommended_market="US"), {"influencer_id": influencer.id}, registry, [], KnowledgeBase(tmp_path / 'knowledge.json'))

    assert task is None


def test_missing_market_influencer_task_is_created_on_a_real_mismatch(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira", market="DE"), categories=["affiliate"])
    registry.save_influencer(influencer)
    opportunity = _opp(recommended_market="US", goal_id="goal-a", product_name="KetoDNA")

    task = _missing_market_influencer_task(opportunity, {"influencer_id": influencer.id}, registry, [], KnowledgeBase(tmp_path / 'knowledge.json'))

    assert task is not None
    assert task.category == "create_asset"
    assert task.goal_id == "goal-a"
    assert task.source_opportunity_id == opportunity.id
    assert "US" in task.description
    assert "Mira" in task.description


def test_missing_market_influencer_task_never_repeats_for_the_same_opportunity(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira", market="DE"), categories=["affiliate"])
    registry.save_influencer(influencer)
    opportunity = _opp(recommended_market="US")
    already_proposed = Task(goal_id="goal-a", description=f"{INFLUENCER_TASK_MARKER} x", category="create_asset", source_opportunity_id=opportunity.id)

    task = _missing_market_influencer_task(opportunity, {"influencer_id": influencer.id}, registry, [already_proposed], KnowledgeBase(tmp_path / 'knowledge.json'))

    assert task is None


# --- _missing_brand_task (isolated, unit-tested before ever being wired
# into advance_decision_driven_campaigns above) --------------------------


def test_missing_brand_task_is_created_unconditionally(tmp_path):
    from atlas.brain.campaign_advance import _missing_brand_task
    opportunity = _opp(product_name="KetoDNA")

    task = _missing_brand_task(opportunity, [], KnowledgeBase(tmp_path / "knowledge.json"))

    assert task is not None
    assert task.category == "create_asset"
    assert task.source_opportunity_id == opportunity.id
    assert task.description.startswith(BRAND_TASK_MARKER)
    assert "KetoDNA" in task.description


def test_missing_brand_task_never_repeats_for_the_same_opportunity(tmp_path):
    from atlas.brain.campaign_advance import _missing_brand_task
    opportunity = _opp()
    already_proposed = Task(goal_id="goal-a", description=f"{BRAND_TASK_MARKER} x", category="create_asset", source_opportunity_id=opportunity.id)

    task = _missing_brand_task(opportunity, [already_proposed], KnowledgeBase(tmp_path / "knowledge.json"))

    assert task is None


def test_missing_brand_task_is_not_deduped_by_an_influencer_proposal_for_the_same_opportunity(tmp_path):
    # A single opportunity can justify both a Brand proposal and a Digital
    # Influencer proposal -- confirms the marker (not just category +
    # source_opportunity_id) is what dedup actually keys on.
    from atlas.brain.campaign_advance import _missing_brand_task
    opportunity = _opp()
    influencer_proposal = Task(
        goal_id="goal-a", description=f"{INFLUENCER_TASK_MARKER} x", category="create_asset", source_opportunity_id=opportunity.id
    )

    task = _missing_brand_task(opportunity, [influencer_proposal], KnowledgeBase(tmp_path / "knowledge.json"))

    assert task is not None


# --- _find_reusable_influencer (isolated, unit-tested before ever being
# wired into advance_decision_driven_campaigns above) --------------------


def _reuse_world(tmp_path):
    from atlas.brain.campaign_advance import _find_reusable_influencer
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    campaigns = CampaignRegistry(tmp_path / "campaigns.json")
    influencers = InfluencerRegistry(tmp_path / "influencers.json")
    return _find_reusable_influencer, memory, kpis, campaigns, influencers


def test_find_reusable_influencer_is_none_when_market_is_unset(tmp_path):
    find, memory, kpis, campaigns, influencers = _reuse_world(tmp_path)
    influencers.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["digital_product"]))

    assert find("", influencers, campaigns, memory, kpis) is None


def test_find_reusable_influencer_is_none_when_no_nationality_matches(tmp_path):
    find, memory, kpis, campaigns, influencers = _reuse_world(tmp_path)
    influencers.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Mira", market="DE"), categories=["digital_product"]))

    assert find("US", influencers, campaigns, memory, kpis) is None


def test_find_reusable_influencer_finds_a_match_from_a_different_category(tmp_path):
    find, memory, kpis, campaigns, influencers = _reuse_world(tmp_path)
    mira = DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["digital_product"])
    influencers.save_influencer(mira)

    reused = find("US", influencers, campaigns, memory, kpis)

    assert reused is not None
    assert reused["influencer_id"] == mira.id


def test_find_reusable_influencer_ignores_retired_influencers(tmp_path):
    find, memory, kpis, campaigns, influencers = _reuse_world(tmp_path)
    influencers.save_influencer(
        DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["digital_product"], status="retired")
    )

    assert find("US", influencers, campaigns, memory, kpis) is None


def test_find_reusable_influencer_prefers_higher_lifetime_value(tmp_path):
    find, memory, kpis, campaigns, influencers = _reuse_world(tmp_path)
    low = DigitalInfluencer(identity=IdentityProfile(name="Low", market="US"), categories=["digital_product"])
    high = DigitalInfluencer(identity=IdentityProfile(name="High", market="US"), categories=["content"])
    influencers.save_influencer(low)
    influencers.save_influencer(high)

    goal_low = Goal(description="low")
    memory.save_goal(goal_low)
    kpis.record(f"revenue_{goal_low.id}", 110.0)
    kpis.record(f"cost_{goal_low.id}", 100.0)  # profit 10
    campaigns.save_campaign(Campaign(business_objective="low", influencer_ids=[low.id], goal_id=goal_low.id))

    goal_high = Goal(description="high")
    memory.save_goal(goal_high)
    kpis.record(f"revenue_{goal_high.id}", 500.0)
    kpis.record(f"cost_{goal_high.id}", 100.0)  # profit 400
    campaigns.save_campaign(Campaign(business_objective="high", influencer_ids=[high.id], goal_id=goal_high.id))

    reused = find("US", influencers, campaigns, memory, kpis)

    assert reused["influencer_id"] == high.id


def test_find_reusable_influencer_falls_back_to_evidence_volume_with_no_measured_value(tmp_path):
    find, memory, kpis, campaigns, influencers = _reuse_world(tmp_path)
    thin = DigitalInfluencer(identity=IdentityProfile(name="Thin", market="US"), categories=["digital_product"])
    rich = DigitalInfluencer(identity=IdentityProfile(name="Rich", market="US"), categories=["content"])
    influencers.save_influencer(thin)
    influencers.save_influencer(rich)
    from atlas.influencer.performance import record_metric
    record_metric(rich.id, "followers", 10000.0, kpis)
    record_metric(rich.id, "views", 50000.0, kpis)

    reused = find("US", influencers, campaigns, memory, kpis)

    assert reused["influencer_id"] == rich.id


def test_reuse_extends_categories_and_completes_the_campaign_when_no_influencer_is_tagged_for_the_category(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, recommended_market="US")
    mira = DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["digital_product"])
    world.influencers.save_influencer(mira)
    # No influencer at all is tagged "affiliate" -- confirms the campaign
    # still gets created by reusing Mira instead of being skipped, and
    # her categories are really extended, not just used transiently.

    world.advance()

    campaigns = world.campaigns.campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].influencer_ids == [mira.id]
    assert world.influencers.get_influencer(mira.id).categories == ["digital_product", "affiliate"]


def test_no_campaign_when_no_influencer_at_all_matches_even_via_reuse(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, recommended_market="US")
    world.influencers.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Mira", market="DE"), categories=["digital_product"]))

    world.advance()

    assert world.campaigns.campaigns() == []


# --- _find_reusable_brand (isolated, unit-tested before ever being wired
# into advance_decision_driven_campaigns above) --------------------------


def _brand_reuse_world(tmp_path):
    from atlas.brain.campaign_advance import _find_reusable_brand
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    campaigns = CampaignRegistry(tmp_path / "campaigns.json")
    brands = BrandRegistry(tmp_path / "brands.json")
    return _find_reusable_brand, memory, kpis, campaigns, brands


def test_find_reusable_brand_is_none_when_niche_is_unset(tmp_path):
    find, memory, kpis, campaigns, brands = _brand_reuse_world(tmp_path)
    brands.save_brand(Brand(name="KetoDNA", niche="KetoDNA"))

    assert find("", brands, campaigns, memory, kpis) is None


def test_find_reusable_brand_is_none_when_no_niche_matches(tmp_path):
    find, memory, kpis, campaigns, brands = _brand_reuse_world(tmp_path)
    brands.save_brand(Brand(name="Other", niche="OtherProduct"))

    assert find("KetoDNA", brands, campaigns, memory, kpis) is None


def test_find_reusable_brand_finds_an_exact_niche_match(tmp_path):
    find, memory, kpis, campaigns, brands = _brand_reuse_world(tmp_path)
    keto = Brand(name="KetoDNA", niche="KetoDNA")
    brands.save_brand(keto)

    reused = find("KetoDNA", brands, campaigns, memory, kpis)

    assert reused is not None
    assert reused.id == keto.id


def test_find_reusable_brand_prefers_higher_lifetime_value_on_a_tie(tmp_path):
    find, memory, kpis, campaigns, brands = _brand_reuse_world(tmp_path)
    low = Brand(name="KetoDNA-1", niche="KetoDNA")
    high = Brand(name="KetoDNA-2", niche="KetoDNA")
    brands.save_brand(low)
    brands.save_brand(high)

    goal_high = Goal(description="high")
    memory.save_goal(goal_high)
    kpis.record(f"revenue_{goal_high.id}", 500.0)
    kpis.record(f"cost_{goal_high.id}", 100.0)  # profit 400
    campaigns.save_campaign(Campaign(business_objective="high", brand_id=high.id, goal_id=goal_high.id))

    reused = find("KetoDNA", brands, campaigns, memory, kpis)

    assert reused.id == high.id


def test_reuse_links_an_existing_brand_instead_of_proposing_a_new_one(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, product_name="KetoDNA")
    world.influencer()
    existing_brand = Brand(name="KetoDNA", niche="KetoDNA")
    world.brands.save_brand(existing_brand)

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    assert campaign.brand_id == existing_brand.id
    # No new Brand Factory proposal -- a real match was reused instead.
    brand_tasks = [t for t in world.memory.tasks() if t.category == "create_asset" and t.description.startswith(BRAND_TASK_MARKER)]
    assert brand_tasks == []


def test_no_matching_brand_still_proposes_creating_one(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = world.selected_opportunity(goal.id, product_name="KetoDNA")
    world.influencer()
    # An unrelated brand exists, but for a different product -- must not match.
    world.brands.save_brand(Brand(name="Other", niche="OtherProduct"))

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    assert campaign.brand_id is None
    brand_tasks = [
        t for t in world.memory.tasks()
        if t.category == "create_asset" and t.source_opportunity_id == opportunity.id and t.description.startswith(BRAND_TASK_MARKER)
    ]
    assert len(brand_tasks) == 1


def test_falls_back_to_top_ranked_influencer_when_no_market_recommendation_exists(tmp_path):
    # Every founder-manual intake today has recommended_market == "" --
    # confirms zero behavior change from before Opportunity Discovery V1.
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.selected_opportunity(goal.id, recommended_market="")
    thin = world.influencer("Thin", market="US")
    rich = world.influencer("Rich", market="DE")
    from atlas.influencer.performance import record_metric
    record_metric(rich.id, "followers", 10000.0, world.kpis)
    record_metric(rich.id, "views", 50000.0, world.kpis)

    world.advance()

    campaign = world.campaigns.campaigns()[0]
    assert campaign.influencer_ids == [rich.id]


def test_missing_market_influencer_raises_a_real_proposal_without_blocking_the_campaign(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = world.selected_opportunity(goal.id, recommended_market="US")
    only_option = world.influencer("Mira", market="DE")  # no influencer speaks US at all

    world.advance()

    # Non-blocking: the campaign still proceeds with the best real
    # influencer available today -- the same "never silently block on a
    # capability gap" behavior propose_capability already has.
    campaign = world.campaigns.campaigns()[0]
    assert campaign.influencer_ids == [only_option.id]

    gap_tasks = [t for t in world.memory.tasks() if t.category == "create_asset" and t.source_opportunity_id == opportunity.id and t.description.startswith(INFLUENCER_TASK_MARKER)]
    assert len(gap_tasks) == 1
    assert "US" in gap_tasks[0].description


def test_missing_market_influencer_proposal_is_not_duplicated_across_repeated_advances(tmp_path):
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    opportunity = world.selected_opportunity(goal.id, recommended_market="US")
    world.influencer("Mira", market="DE")

    world.advance()
    world.advance()
    world.advance()

    gap_tasks = [t for t in world.memory.tasks() if t.category == "create_asset" and t.source_opportunity_id == opportunity.id and t.description.startswith(INFLUENCER_TASK_MARKER)]
    assert len(gap_tasks) == 1
