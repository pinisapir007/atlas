from atlas.brain.capital_allocation import recommend_allocation
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, StrategicObjective
from atlas.brand.registry import BrandRegistry
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry


def _world(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    campaigns = CampaignRegistry(tmp_path / "campaigns.json")
    influencers = InfluencerRegistry(tmp_path / "influencers.json")
    brands = BrandRegistry(tmp_path / "brands.json")
    return knowledge, memory, kpis, influencers, brands, campaigns


def _sourced_finding(category: str, i: int) -> Finding:
    return Finding(source="research", category=category, description=f"signal {i}", evidence=f"https://example.com/{i}")


def test_holds_when_evaluate_has_not_cleared_the_category(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))  # only one source -- below the evidence bar

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert rec.action == "insufficient_evidence"
    assert rec.decision.verdict == "insufficient_evidence"
    assert "not cleared" in rec.reasoning


def test_recommends_investing_new_when_cleared_and_no_proven_asset_exists(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))
    knowledge.save_finding(_sourced_finding("affiliate", 2))

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert rec.decision.verdict == "invest"
    assert rec.action == "invest_new"
    assert rec.best_existing_asset is None


def test_recommends_strengthening_a_real_proven_existing_asset_instead_of_a_new_one(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))
    knowledge.save_finding(_sourced_finding("affiliate", 2))

    influencer = DigitalInfluencer(identity=IdentityProfile(name="Maya", market="US"), categories=["affiliate"])
    influencers.save_influencer(influencer)
    goal = Goal(description="existing affiliate engine")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 500.0)
    kpis.record(f"cost_{goal.id}", 100.0)  # real profit 400
    campaigns.save_campaign(Campaign(business_objective="c", influencer_ids=[influencer.id], goal_id=goal.id))

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert rec.action == "strengthen_existing"
    assert rec.best_existing_asset.asset_id == influencer.id
    assert rec.best_existing_asset.lifetime_value == 400.0
    assert "400.00" in rec.reasoning
    assert "Maya" in rec.reasoning


def test_an_unproven_existing_asset_does_not_block_investing_new(tmp_path):
    # A real asset tagged for the category, but with zero measured
    # profit yet (None lifetime value) -- must not be treated as
    # "proven"; that would silently block a real, evidence-cleared
    # investment on an asset that hasn't earned anything yet.
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))
    knowledge.save_finding(_sourced_finding("affiliate", 2))
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Unproven"), categories=["affiliate"])
    influencers.save_influencer(influencer)

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert rec.action == "invest_new"
    assert rec.best_existing_asset.lifetime_value is None


def test_a_portfolio_asset_in_a_different_category_is_never_recommended(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))
    knowledge.save_finding(_sourced_finding("affiliate", 2))
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Wrong niche"), categories=["digital_product"])
    influencers.save_influencer(influencer)

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert rec.action == "invest_new"
    assert rec.best_existing_asset is None


def test_surfaces_a_real_pause_candidate_from_the_actual_strategist(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))
    knowledge.save_finding(_sourced_finding("affiliate", 2))

    strong = Goal(description="strong performer", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="failing engine", founder_estimate={"expected_revenue": 100.0})
    memory.save_goal(strong)
    memory.save_goal(weak)
    for value in (50.0, 50.0, 50.0):
        kpis.record(f"revenue_{weak.id}", value)

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert len(rec.pause_candidates) == 1
    assert rec.pause_candidates[0]["goal_id"] == weak.id
    assert "failing engine" in rec.reasoning


def test_lists_real_registered_ai_providers_informationally(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert "gemini" in rec.ai_providers_note
    assert "claude" in rec.ai_providers_note
    assert "no quota enforced yet" in rec.ai_providers_note


def test_objective_id_is_none_when_no_objective_is_passed(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns)

    assert rec.objective_id is None


def test_objective_id_is_recorded_when_a_real_objective_is_passed(tmp_path):
    knowledge, memory, kpis, influencers, brands, campaigns = _world(tmp_path)
    knowledge.save_finding(_sourced_finding("affiliate", 1))
    objective = StrategicObjective(
        description="first $1,000", target_metric="revenue", target_value=1000.0,
        cash_flow_weight=1.0, strategic_value_weight=0.0,
    )

    rec = recommend_allocation("affiliate", knowledge, memory, kpis, influencers, brands, campaigns, objective=objective)

    assert rec.objective_id == objective.id
