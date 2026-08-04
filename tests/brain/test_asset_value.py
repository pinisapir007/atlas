from atlas.brain.asset_value import (
    brand_lifetime_value,
    influencer_lifetime_value,
    rank_success_laws_by_track_record,
    success_law_lifetime_value,
)
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, SuccessLaw
from atlas.campaign.registry import CampaignRegistry
from atlas.campaign.models import Campaign


def _memory(tmp_path) -> BrainMemory:
    return BrainMemory(tmp_path / "brain.json")


def _campaigns(tmp_path) -> CampaignRegistry:
    return CampaignRegistry(tmp_path / "campaigns.json")


def test_none_when_influencer_is_part_of_no_campaign(tmp_path):
    memory, campaigns, kpis = _memory(tmp_path), _campaigns(tmp_path), None
    kpis = KPIRegistry(memory)

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) is None


def test_none_when_campaigns_exist_but_nothing_is_measured_yet(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="g")
    memory.save_goal(goal)
    campaigns.save_campaign(Campaign(business_objective="o", influencer_ids=["influencer-x"], goal_id=goal.id))

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) is None


def test_sums_real_profit_across_every_campaign_this_influencer_was_part_of(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)

    goal_a = Goal(description="a")
    memory.save_goal(goal_a)
    kpis.record(f"revenue_{goal_a.id}", 200.0)
    kpis.record(f"cost_{goal_a.id}", 50.0)  # profit 150
    campaigns.save_campaign(Campaign(business_objective="a", influencer_ids=["influencer-x"], goal_id=goal_a.id))

    goal_b = Goal(description="b")
    memory.save_goal(goal_b)
    kpis.record(f"revenue_{goal_b.id}", 100.0)
    kpis.record(f"cost_{goal_b.id}", 80.0)  # profit 20
    campaigns.save_campaign(Campaign(business_objective="b", influencer_ids=["influencer-x"], goal_id=goal_b.id))

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) == 170.0


def test_ignores_campaigns_a_different_influencer_was_part_of(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 500.0)
    kpis.record(f"cost_{goal.id}", 100.0)
    campaigns.save_campaign(Campaign(business_objective="a", influencer_ids=["influencer-other"], goal_id=goal.id))

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) is None


def test_counts_a_campaign_with_multiple_influencers_once_for_each(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 300.0)
    kpis.record(f"cost_{goal.id}", 100.0)  # profit 200
    campaigns.save_campaign(Campaign(business_objective="a", influencer_ids=["influencer-x", "influencer-y"], goal_id=goal.id))

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) == 200.0
    assert influencer_lifetime_value("influencer-y", campaigns, memory, kpis) == 200.0


def test_ignores_a_campaign_with_no_goal_id(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    campaigns.save_campaign(Campaign(business_objective="a", influencer_ids=["influencer-x"], goal_id=None))

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) is None


def test_sums_profit_across_campaigns_only_once_even_if_goal_shared(tmp_path):
    # Two campaigns pointing at the same goal (shouldn't happen in
    # practice, but the dedup via a set of goal_ids protects against
    # double-counting the same real profit twice).
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 300.0)
    kpis.record(f"cost_{goal.id}", 100.0)  # profit 200
    campaigns.save_campaign(Campaign(business_objective="a", influencer_ids=["influencer-x"], goal_id=goal.id))
    campaigns.save_campaign(Campaign(business_objective="a-dup", influencer_ids=["influencer-x"], goal_id=goal.id))

    assert influencer_lifetime_value("influencer-x", campaigns, memory, kpis) == 200.0


# --- brand_lifetime_value ------------------------------------------------


def test_brand_none_when_part_of_no_campaign(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)

    assert brand_lifetime_value("brand-x", campaigns, memory, kpis) is None


def test_brand_sums_real_profit_across_every_linked_campaign(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)

    goal_a = Goal(description="a")
    memory.save_goal(goal_a)
    kpis.record(f"revenue_{goal_a.id}", 200.0)
    kpis.record(f"cost_{goal_a.id}", 50.0)  # profit 150
    campaigns.save_campaign(Campaign(business_objective="a", brand_id="brand-x", goal_id=goal_a.id))

    goal_b = Goal(description="b")
    memory.save_goal(goal_b)
    kpis.record(f"revenue_{goal_b.id}", 100.0)
    kpis.record(f"cost_{goal_b.id}", 80.0)  # profit 20
    campaigns.save_campaign(Campaign(business_objective="b", brand_id="brand-x", goal_id=goal_b.id))

    assert brand_lifetime_value("brand-x", campaigns, memory, kpis) == 170.0


def test_brand_ignores_a_campaign_linked_to_a_different_brand(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 500.0)
    kpis.record(f"cost_{goal.id}", 100.0)
    campaigns.save_campaign(Campaign(business_objective="a", brand_id="brand-other", goal_id=goal.id))

    assert brand_lifetime_value("brand-x", campaigns, memory, kpis) is None


def test_brand_ignores_a_campaign_with_no_brand_linked(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 500.0)
    kpis.record(f"cost_{goal.id}", 100.0)
    campaigns.save_campaign(Campaign(business_objective="a", brand_id=None, goal_id=goal.id))

    assert brand_lifetime_value("brand-x", campaigns, memory, kpis) is None


# --- success_law_lifetime_value ------------------------------------------


def test_law_none_when_no_campaign_was_created_with_it_in_effect(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)

    assert success_law_lifetime_value("law-x", campaigns, memory, kpis) is None


def test_law_sums_real_profit_across_every_campaign_it_was_relevant_for(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)

    goal_a = Goal(description="a")
    memory.save_goal(goal_a)
    kpis.record(f"revenue_{goal_a.id}", 200.0)
    kpis.record(f"cost_{goal_a.id}", 50.0)  # profit 150
    campaigns.save_campaign(Campaign(business_objective="a", success_law_ids=["law-x"], goal_id=goal_a.id))

    goal_b = Goal(description="b")
    memory.save_goal(goal_b)
    kpis.record(f"revenue_{goal_b.id}", 100.0)
    kpis.record(f"cost_{goal_b.id}", 80.0)  # profit 20
    campaigns.save_campaign(Campaign(business_objective="b", success_law_ids=["law-x"], goal_id=goal_b.id))

    assert success_law_lifetime_value("law-x", campaigns, memory, kpis) == 170.0


def test_law_ignores_a_campaign_that_did_not_have_it_in_effect(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 500.0)
    kpis.record(f"cost_{goal.id}", 100.0)
    campaigns.save_campaign(Campaign(business_objective="a", success_law_ids=["law-other"], goal_id=goal.id))

    assert success_law_lifetime_value("law-x", campaigns, memory, kpis) is None


def test_law_reflects_a_real_negative_outcome_honestly(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="a")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 50.0)
    kpis.record(f"cost_{goal.id}", 200.0)  # profit -150
    campaigns.save_campaign(Campaign(business_objective="a", success_law_ids=["law-x"], goal_id=goal.id))

    assert success_law_lifetime_value("law-x", campaigns, memory, kpis) == -150.0


# --- rank_success_laws_by_track_record -----------------------------------


def test_rank_prefers_a_real_positive_track_record(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    winner = SuccessLaw(principle="winner", source_description="s")
    loser = SuccessLaw(principle="loser", source_description="s")

    goal_w = Goal(description="w")
    memory.save_goal(goal_w)
    kpis.record(f"revenue_{goal_w.id}", 500.0)
    kpis.record(f"cost_{goal_w.id}", 100.0)  # profit 400
    campaigns.save_campaign(Campaign(business_objective="w", success_law_ids=[winner.id], goal_id=goal_w.id))

    goal_l = Goal(description="l")
    memory.save_goal(goal_l)
    kpis.record(f"revenue_{goal_l.id}", 50.0)
    kpis.record(f"cost_{goal_l.id}", 200.0)  # profit -150
    campaigns.save_campaign(Campaign(business_objective="l", success_law_ids=[loser.id], goal_id=goal_l.id))

    ranked = rank_success_laws_by_track_record([loser, winner], campaigns, memory, kpis)

    assert [law.principle for law in ranked] == ["winner", "loser"]


def test_rank_prefers_a_real_measured_law_over_an_unmeasured_one(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    measured = SuccessLaw(principle="measured", source_description="s")
    unmeasured = SuccessLaw(principle="unmeasured", source_description="s")

    goal = Goal(description="g")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"cost_{goal.id}", 50.0)  # profit 50, even a small positive beats "unknown"
    campaigns.save_campaign(Campaign(business_objective="g", success_law_ids=[measured.id], goal_id=goal.id))

    ranked = rank_success_laws_by_track_record([unmeasured, measured], campaigns, memory, kpis)

    assert [law.principle for law in ranked] == ["measured", "unmeasured"]


def test_rank_preserves_input_order_among_laws_with_no_track_record_yet(tmp_path):
    memory, campaigns = _memory(tmp_path), _campaigns(tmp_path)
    kpis = KPIRegistry(memory)
    first = SuccessLaw(principle="first", source_description="s")
    second = SuccessLaw(principle="second", source_description="s")

    ranked = rank_success_laws_by_track_record([first, second], campaigns, memory, kpis)

    assert [law.principle for law in ranked] == ["first", "second"]
