import pytest

from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Task
from atlas.brand.factory import (
    TASK_MARKER,
    BrandDraft,
    create_brand_from_proposal,
    draft_brand_proposal,
    suggest_brand,
)
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry, create_campaign
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _opportunity(marketing_niche="KetoDNA", recommended_market="US", category="affiliate", product_name="KetoDNA") -> AffiliateOpportunity:
    return AffiliateOpportunity(
        product_name=product_name, description="d", category=category, marketing_niche=marketing_niche, recommended_market=recommended_market
    )


# --- draft_brand_proposal ---------------------------------------------


def test_draft_cites_real_evidence_and_defaults_name_to_the_real_product(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA"))
    kb.save_finding(Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="KetoDNA"))
    opportunity = _opportunity()

    draft = draft_brand_proposal(opportunity, kb)

    assert draft.recommended_name == "KetoDNA"
    assert draft.recommended_niche == "KetoDNA"
    assert draft.recommended_category == "affiliate"
    assert draft.recommended_market == "US"
    assert draft.source_opportunity_id == opportunity.id
    assert set(draft.evidence) == {"https://x/1", "https://x/2"}
    assert "2 independent source" in draft.rationale


def test_draft_never_fabricates_evidence_when_none_is_tagged(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="US")

    draft = draft_brand_proposal(opportunity, kb)

    assert draft.evidence == []
    assert "no cited evidence" in draft.rationale


def test_draft_is_honest_about_no_market_recommendation(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="")

    draft = draft_brand_proposal(opportunity, kb)

    assert "No market-specific evidence" in draft.rationale


# --- suggest_brand ------------------------------------------------------


def _draft(niche="KetoDNA", opportunity_id="aopp-fixed-1") -> BrandDraft:
    return BrandDraft(
        recommended_name=niche, recommended_niche=niche, recommended_category="affiliate",
        recommended_market="US", source_opportunity_id=opportunity_id, rationale="r",
    )


def test_suggest_brand_is_deterministic_for_the_same_opportunity():
    draft = _draft()

    assert suggest_brand(draft) == suggest_brand(draft)


def test_suggest_brand_can_differ_across_different_opportunities():
    a = suggest_brand(_draft(opportunity_id="aopp-1"))
    b = suggest_brand(_draft(opportunity_id="aopp-2"))
    c = suggest_brand(_draft(opportunity_id="aopp-3"))

    assert len({a.tagline, b.tagline, c.tagline}) > 1


def test_suggest_brand_every_field_is_non_empty():
    suggestion = suggest_brand(_draft())

    assert suggestion.tagline
    assert suggestion.visual_identity
    assert suggestion.voice


def test_suggest_brand_tagline_references_the_real_niche():
    suggestion = suggest_brand(_draft(niche="KetoDNA"))

    assert "KetoDNA" in suggestion.tagline


# --- create_brand_from_proposal -----------------------------------------


class _World:
    def __init__(self, tmp_path):
        self.memory = BrainMemory(tmp_path / "brain.json")
        self.knowledge = KnowledgeBase(tmp_path / "knowledge.json")
        self.affiliate_store = AffiliateStore(tmp_path / "affiliate_intelligence.json")
        self.brands = BrandRegistry(tmp_path / "brands.json")
        self.influencers = InfluencerRegistry(tmp_path / "influencers.json")
        self.campaigns = CampaignRegistry(tmp_path / "campaigns.json")

    def approved_proposal_task(self, market="US", niche="KetoDNA", category="affiliate", goal_id="goal-a") -> Task:
        opportunity = AffiliateOpportunity(
            product_name=niche, description="d", category=category, marketing_niche=niche, recommended_market=market, goal_id=goal_id,
        )
        self.affiliate_store.save_opportunity(opportunity)
        task = Task(goal_id=goal_id, description=f"{TASK_MARKER} recommend creating a new brand", category="create_asset", source_opportunity_id=opportunity.id)
        task.transition("done", "proposal applied")  # simulates a real brain approve()
        self.memory.save_task(task)
        return task


def test_creates_a_real_brand_from_an_approved_proposal_with_explicit_overrides(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(market="US", niche="KetoDNA", category="affiliate")

    brand = create_brand_from_proposal(
        task.id, world.memory, world.affiliate_store, world.knowledge, world.brands,
        name="KetoDNA Co", tagline="Custom tagline",
    )

    assert brand.name == "KetoDNA Co"
    assert brand.tagline == "Custom tagline"
    assert brand.niche == "KetoDNA"
    assert brand.category == "affiliate"
    assert brand.market == "US"
    assert world.brands.get_brand(brand.id).name == "KetoDNA Co"


def test_creation_defaults_every_field_to_the_real_or_suggested_value_when_omitted(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(market="US", niche="KetoDNA", category="affiliate")
    opportunity = world.affiliate_store.get_opportunity(task.source_opportunity_id)
    draft = draft_brand_proposal(opportunity, world.knowledge)
    expected = suggest_brand(draft)

    brand = create_brand_from_proposal(task.id, world.memory, world.affiliate_store, world.knowledge, world.brands)

    assert brand.name == draft.recommended_name  # real fact, not fabricated
    assert brand.tagline == expected.tagline
    assert brand.visual_identity == expected.visual_identity
    assert brand.voice == expected.voice


def test_rejects_a_task_that_is_not_a_brand_factory_proposal(tmp_path):
    world = _World(tmp_path)
    # An Influencer Factory proposal for the same opportunity -- same
    # category and source_opportunity_id, different marker.
    opportunity = AffiliateOpportunity(product_name="KetoDNA", description="d", category="affiliate", recommended_market="US")
    world.affiliate_store.save_opportunity(opportunity)
    influencer_task = Task(
        goal_id="goal-a", description="Digital Influencer Factory: recommend creating a new influencer",
        category="create_asset", source_opportunity_id=opportunity.id,
    )
    influencer_task.transition("done", "x")
    world.memory.save_task(influencer_task)

    with pytest.raises(ValueError, match="not a Brand Factory proposal"):
        create_brand_from_proposal(influencer_task.id, world.memory, world.affiliate_store, world.knowledge, world.brands)


def test_rejects_creation_before_approval(tmp_path):
    world = _World(tmp_path)
    opportunity = AffiliateOpportunity(product_name="KetoDNA", description="d", category="affiliate", recommended_market="US")
    world.affiliate_store.save_opportunity(opportunity)
    unapproved_task = Task(
        goal_id="goal-a", description=f"{TASK_MARKER} recommend creating a new brand",
        category="create_asset", source_opportunity_id=opportunity.id,
    )
    world.memory.save_task(unapproved_task)  # still "proposed" -- never approved

    with pytest.raises(ValueError, match="has not been approved yet"):
        create_brand_from_proposal(unapproved_task.id, world.memory, world.affiliate_store, world.knowledge, world.brands)


def test_rejects_a_rejected_proposal(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task()
    task.transition("failed", "rejected by owner")
    world.memory.save_task(task)

    with pytest.raises(ValueError, match="has not been approved yet"):
        create_brand_from_proposal(task.id, world.memory, world.affiliate_store, world.knowledge, world.brands)


def test_auto_links_the_real_campaign_for_the_same_goal(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(goal_id="goal-a")
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira"), categories=["affiliate"])
    world.influencers.save_influencer(influencer)
    from atlas.brain.kpi import KPIRegistry
    kpis = KPIRegistry(world.memory)
    campaign = create_campaign(
        "objective", "affiliate", "KetoDNA", [influencer.id], world.influencers, world.knowledge, world.memory, kpis,
        registry=world.campaigns, goal_id="goal-a",
    )
    assert campaign.brand_id is None

    brand = create_brand_from_proposal(
        task.id, world.memory, world.affiliate_store, world.knowledge, world.brands, campaign_registry=world.campaigns,
    )

    linked = world.campaigns.get_campaign(campaign.id)
    assert linked.brand_id == brand.id


def test_does_not_link_a_campaign_for_a_different_goal(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(goal_id="goal-a")
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira"), categories=["affiliate"])
    world.influencers.save_influencer(influencer)
    from atlas.brain.kpi import KPIRegistry
    kpis = KPIRegistry(world.memory)
    campaign = create_campaign(
        "objective", "affiliate", "OtherProduct", [influencer.id], world.influencers, world.knowledge, world.memory, kpis,
        registry=world.campaigns, goal_id="goal-elsewhere",
    )

    create_brand_from_proposal(
        task.id, world.memory, world.affiliate_store, world.knowledge, world.brands, campaign_registry=world.campaigns,
    )

    assert world.campaigns.get_campaign(campaign.id).brand_id is None


def test_no_campaign_registry_given_still_creates_the_brand(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task()

    brand = create_brand_from_proposal(task.id, world.memory, world.affiliate_store, world.knowledge, world.brands)

    assert brand.id in {b.id for b in world.brands.brands()}
