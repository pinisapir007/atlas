from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal
from atlas.brain.portfolio import portfolio_entries, rank_portfolio
from atlas.brand.models import Brand
from atlas.brand.registry import BrandRegistry
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry


def _world(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    campaigns = CampaignRegistry(tmp_path / "campaigns.json")
    influencers = InfluencerRegistry(tmp_path / "influencers.json")
    brands = BrandRegistry(tmp_path / "brands.json")
    return memory, kpis, campaigns, influencers, brands


def test_empty_portfolio_when_nothing_has_been_created(tmp_path):
    memory, kpis, campaigns, influencers, brands = _world(tmp_path)

    assert portfolio_entries(influencers, brands, campaigns, memory, kpis) == []


def test_includes_a_real_active_influencer(tmp_path):
    memory, kpis, campaigns, influencers, brands = _world(tmp_path)
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Maya", market="US"), categories=["affiliate", "digital_product"])
    influencers.save_influencer(influencer)

    entries = portfolio_entries(influencers, brands, campaigns, memory, kpis)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.asset_type == "digital_influencer"
    assert entry.asset_id == influencer.id
    assert entry.name == "Maya"
    assert entry.market == "US"
    assert entry.business_models == ["affiliate", "digital_product"]
    assert entry.lifetime_value is None  # no measured campaigns yet


def test_excludes_a_retired_influencer(tmp_path):
    memory, kpis, campaigns, influencers, brands = _world(tmp_path)
    influencers.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Retired"), status="retired"))

    assert portfolio_entries(influencers, brands, campaigns, memory, kpis) == []


def test_includes_a_real_brand(tmp_path):
    memory, kpis, campaigns, influencers, brands = _world(tmp_path)
    brand = Brand(name="KetoDNA", niche="KetoDNA", category="affiliate", market="US")
    brands.save_brand(brand)

    entries = portfolio_entries(influencers, brands, campaigns, memory, kpis)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.asset_type == "brand"
    assert entry.asset_id == brand.id
    assert entry.name == "KetoDNA"
    assert entry.business_models == ["affiliate"]


def test_includes_real_measured_lifetime_value_for_both_types(tmp_path):
    memory, kpis, campaigns, influencers, brands = _world(tmp_path)
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Maya"), categories=["affiliate"])
    influencers.save_influencer(influencer)
    brand = Brand(name="KetoDNA", niche="KetoDNA")
    brands.save_brand(brand)

    goal = Goal(description="g")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 300.0)
    kpis.record(f"cost_{goal.id}", 100.0)  # profit 200
    campaigns.save_campaign(Campaign(business_objective="c", influencer_ids=[influencer.id], brand_id=brand.id, goal_id=goal.id))

    entries = {e.asset_type: e for e in portfolio_entries(influencers, brands, campaigns, memory, kpis)}

    assert entries["digital_influencer"].lifetime_value == 200.0
    assert entries["brand"].lifetime_value == 200.0


def test_rank_portfolio_orders_by_lifetime_value_descending_none_last(tmp_path):
    memory, kpis, campaigns, influencers, brands = _world(tmp_path)
    low = DigitalInfluencer(identity=IdentityProfile(name="Low"))
    high = DigitalInfluencer(identity=IdentityProfile(name="High"))
    unmeasured = DigitalInfluencer(identity=IdentityProfile(name="Unmeasured"))
    influencers.save_influencer(low)
    influencers.save_influencer(high)
    influencers.save_influencer(unmeasured)

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

    ranked = rank_portfolio(portfolio_entries(influencers, brands, campaigns, memory, kpis))

    assert [e.name for e in ranked] == ["High", "Low", "Unmeasured"]
