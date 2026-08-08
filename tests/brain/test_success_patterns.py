from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal
from atlas.brain.success_patterns import best_pattern_for_category, identify_success_patterns
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _setup():
    memory = BrainMemory(store=_FakeStore())
    kpis = KPIRegistry(memory)
    campaigns = CampaignRegistry(store=_FakeStore())
    return memory, kpis, campaigns


def _campaign_with_profit(memory, kpis, campaigns, category, content_formats, platform_strategy, revenue, cost):
    goal = Goal(description=f"{category} goal", status="active")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", revenue)
    kpis.record(f"cost_{goal.id}", cost)
    campaign = Campaign(
        business_objective="d",
        category=category,
        product_offer="p",
        goal_id=goal.id,
        content_formats=content_formats,
        platform_strategy=platform_strategy,
    )
    campaigns.save_campaign(campaign)
    return campaign


def test_returns_no_pattern_with_fewer_than_two_supporting_campaigns():
    memory, kpis, campaigns = _setup()
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=100.0, cost=20.0)

    patterns = identify_success_patterns("affiliate", campaigns, memory, kpis)

    assert patterns == []


def test_identifies_a_real_pattern_from_two_supporting_campaigns():
    memory, kpis, campaigns = _setup()
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=100.0, cost=20.0)
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=150.0, cost=30.0)

    patterns = identify_success_patterns("affiliate", campaigns, memory, kpis)

    assert len(patterns) == 1
    assert patterns[0].content_formats == ["video"]
    assert patterns[0].platform_strategy == "TikTok"
    assert patterns[0].campaign_count == 2
    assert patterns[0].average_profit == 100.0  # (80 + 120) / 2


def test_ranks_the_higher_real_profit_combination_first():
    memory, kpis, campaigns = _setup()
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=100.0, cost=90.0)
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=100.0, cost=90.0)
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["image", "caption"], "Instagram", revenue=500.0, cost=50.0)
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["image", "caption"], "Instagram", revenue=500.0, cost=50.0)

    patterns = identify_success_patterns("affiliate", campaigns, memory, kpis)

    assert len(patterns) == 2
    assert patterns[0].platform_strategy == "Instagram"
    assert patterns[0].average_profit == 450.0
    assert patterns[1].platform_strategy == "TikTok"


def test_ignores_campaigns_with_no_declared_content_formats_or_platform_strategy():
    memory, kpis, campaigns = _setup()
    goal = Goal(description="g", status="active")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"cost_{goal.id}", 10.0)
    campaigns.save_campaign(Campaign(business_objective="d", category="affiliate", product_offer="p", goal_id=goal.id))

    patterns = identify_success_patterns("affiliate", campaigns, memory, kpis)

    assert patterns == []


def test_ignores_campaigns_with_no_measured_profit():
    memory, kpis, campaigns = _setup()
    goal = Goal(description="g", status="active")
    memory.save_goal(goal)
    campaigns.save_campaign(
        Campaign(business_objective="d", category="affiliate", product_offer="p", goal_id=goal.id, content_formats=["video"], platform_strategy="TikTok")
    )

    patterns = identify_success_patterns("affiliate", campaigns, memory, kpis)

    assert patterns == []


def test_ignores_campaigns_in_a_different_category():
    memory, kpis, campaigns = _setup()
    _campaign_with_profit(memory, kpis, campaigns, "digital_product", ["video"], "TikTok", revenue=100.0, cost=10.0)
    _campaign_with_profit(memory, kpis, campaigns, "digital_product", ["video"], "TikTok", revenue=100.0, cost=10.0)

    patterns = identify_success_patterns("affiliate", campaigns, memory, kpis)

    assert patterns == []


def test_best_pattern_for_category_returns_none_when_no_pattern_exists():
    memory, kpis, campaigns = _setup()

    result = best_pattern_for_category("affiliate", campaigns, memory, kpis)

    assert result is None


def test_best_pattern_for_category_returns_the_top_real_pattern():
    memory, kpis, campaigns = _setup()
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=100.0, cost=10.0)
    _campaign_with_profit(memory, kpis, campaigns, "affiliate", ["video"], "TikTok", revenue=100.0, cost=10.0)

    result = best_pattern_for_category("affiliate", campaigns, memory, kpis)

    assert result.content_formats == ["video"]
    assert result.platform_strategy == "TikTok"
