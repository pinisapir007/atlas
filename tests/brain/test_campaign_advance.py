from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.campaign_advance import advance_decision_driven_campaigns
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal
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
        self.execution_plans = ExecutionPlanRegistry(tmp_path / "execution_plans.json")
        self.affiliate_store = AffiliateStore(tmp_path / "affiliate_intelligence.json")

    def advance(self):
        advance_decision_driven_campaigns(
            self.memory, self.knowledge, self.kpis, self.influencers, self.campaigns, self.execution_plans, self.affiliate_store
        )

    def decision_engine_goal(self, category="affiliate", status="active") -> Goal:
        goal = Goal(description=f"Pursue {category} opportunities", engine_id=f"intelligence_{category}", status=status)
        self.memory.save_goal(goal)
        return goal

    def selected_opportunity(self, goal_id, product_name="KetoDNA", real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/") -> AffiliateOpportunity:
        opportunity = AffiliateOpportunity(
            product_name=product_name, description="a real product", goal_id=goal_id, stage="selected_for_marketing",
            real_affiliate_link=real_affiliate_link,
        )
        self.affiliate_store.save_opportunity(opportunity)
        return opportunity

    def influencer(self, name="Mira", categories=("affiliate",)) -> DigitalInfluencer:
        influencer = DigitalInfluencer(identity=IdentityProfile(name=name), categories=list(categories))
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
