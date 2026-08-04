import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry, create_campaign, link_destination_url, refresh_confidence
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry


def _influencer_registry(tmp_path) -> InfluencerRegistry:
    return InfluencerRegistry(tmp_path / "influencers.json")


def _campaign_registry(tmp_path) -> CampaignRegistry:
    return CampaignRegistry(tmp_path / "campaigns.json")


def _knowledge(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path) -> BrainMemory:
    return BrainMemory(tmp_path / "brain.json")


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(_memory(tmp_path))


def _new_influencer(registry, name="Mira") -> DigitalInfluencer:
    influencer = DigitalInfluencer(identity=IdentityProfile(name=name), categories=["affiliate"])
    registry.save_influencer(influencer)
    return influencer


# --- CampaignRegistry (pure CRUD) ------------------------------------------


def test_round_trips_a_campaign(tmp_path):
    registry = _campaign_registry(tmp_path)
    campaign = Campaign(business_objective="grow affiliate revenue", category="affiliate", product_offer="KetoDNA", influencer_ids=["influencer-a"])
    registry.save_campaign(campaign)

    reloaded = CampaignRegistry(tmp_path / "campaigns.json").get_campaign(campaign.id)
    assert reloaded.business_objective == "grow affiliate revenue"
    assert reloaded.product_offer == "KetoDNA"
    assert reloaded.influencer_ids == ["influencer-a"]
    assert reloaded.status == "proposed"


def test_missing_campaign_raises_keyerror(tmp_path):
    registry = _campaign_registry(tmp_path)
    with pytest.raises(KeyError):
        registry.get_campaign("does-not-exist")


def test_campaigns_lists_every_saved_campaign(tmp_path):
    registry = _campaign_registry(tmp_path)
    registry.save_campaign(Campaign(business_objective="a"))
    registry.save_campaign(Campaign(business_objective="b"))

    assert len(registry.campaigns()) == 2


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "campaigns.json"
    registry = CampaignRegistry(path)
    registry.save_campaign(Campaign(business_objective="a"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()


def test_revenue_goal_and_budget_default_to_none_never_a_fabricated_guess(tmp_path):
    campaign = Campaign(business_objective="a")

    assert campaign.revenue_goal is None
    assert campaign.budget is None
    assert campaign.confidence_score is None


# --- create_campaign() ------------------------------------------------------


def test_create_campaign_rejects_an_unknown_influencer_id(tmp_path):
    with pytest.raises(ValueError):
        create_campaign(
            business_objective="grow affiliate revenue",
            category="affiliate",
            product_offer="KetoDNA",
            influencer_ids=["does-not-exist"],
            influencer_registry=_influencer_registry(tmp_path),
            knowledge=_knowledge(tmp_path),
            memory=_memory(tmp_path),
            kpis=_kpis(tmp_path),
            registry=_campaign_registry(tmp_path),
        )


def test_create_campaign_persists_and_returns_a_real_campaign(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    campaign_registry = _campaign_registry(tmp_path)

    campaign = create_campaign(
        business_objective="grow affiliate revenue",
        category="affiliate",
        product_offer="KetoDNA",
        influencer_ids=[influencer.id],
        influencer_registry=influencer_registry,
        knowledge=_knowledge(tmp_path),
        memory=_memory(tmp_path),
        kpis=_kpis(tmp_path),
        registry=campaign_registry,
        revenue_goal=5000.0,
        target_audience="keto beginners",
        customer_problem="can't tell if keto is working",
        platform_strategy="TikTok first, cross-post to Instagram",
        content_strategy="myth-busting short-form video",
        content_formats=["short-form video"],
        landing_page_strategy="single offer page, no upsell",
        cta_strategy="link in bio",
        budget=500.0,
        timeline={"start": "2026-09-01", "end": "2026-10-01"},
        success_kpis=["revenue_goal-a"],
        goal_id="goal-a",
    )

    reloaded = campaign_registry.get_campaign(campaign.id)
    assert reloaded.business_objective == "grow affiliate revenue"
    assert reloaded.revenue_goal == 5000.0
    assert reloaded.target_audience == "keto beginners"
    assert reloaded.platform_strategy == "TikTok first, cross-post to Instagram"
    assert reloaded.content_formats == ["short-form video"]
    assert reloaded.budget == 500.0
    assert reloaded.timeline == {"start": "2026-09-01", "end": "2026-10-01"}
    assert reloaded.success_kpis == ["revenue_goal-a"]
    assert reloaded.goal_id == "goal-a"


def test_create_campaign_computes_a_real_confidence_score_not_a_fabricated_one(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    knowledge = _knowledge(tmp_path)

    # No evidence at all yet -> confidence must be None, never a guessed default.
    empty = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=knowledge, memory=_memory(tmp_path), kpis=_kpis(tmp_path),
        registry=_campaign_registry(tmp_path),
    )
    assert empty.confidence_score is None

    # Real evidence added -> confidence becomes a real, non-None number,
    # reusing the exact Intelligence Layer confidence_score() the Decision
    # Engine itself already computes from.
    knowledge.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    with_evidence = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=knowledge, memory=_memory(tmp_path), kpis=_kpis(tmp_path),
        registry=_campaign_registry(tmp_path),
    )
    assert with_evidence.confidence_score is not None


def test_create_campaign_records_an_initial_learning_history_entry(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)

    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=_knowledge(tmp_path), memory=_memory(tmp_path), kpis=_kpis(tmp_path),
        registry=_campaign_registry(tmp_path),
    )

    assert len(campaign.learning_history) == 1
    assert campaign.learning_history[0]["event"] == "campaign_created"


# --- refresh_confidence() ---------------------------------------------------


def test_refresh_confidence_updates_the_score_and_appends_learning_history(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    knowledge, memory, kpis = _knowledge(tmp_path), _memory(tmp_path), _kpis(tmp_path)
    campaign_registry = _campaign_registry(tmp_path)

    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=knowledge, memory=memory, kpis=kpis, registry=campaign_registry,
    )
    assert campaign.confidence_score is None

    knowledge.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    updated = refresh_confidence(campaign.id, knowledge, memory, kpis, campaign_registry)

    assert updated.confidence_score is not None
    assert len(updated.learning_history) == 2
    assert updated.learning_history[-1]["event"] == "confidence_refreshed"
    assert updated.learning_history[-1]["previous_confidence"] is None
    assert updated.learning_history[-1]["new_confidence"] == updated.confidence_score
    # persisted, not just returned in-memory
    assert campaign_registry.get_campaign(campaign.id).confidence_score == updated.confidence_score


def test_refresh_confidence_reacts_to_real_measured_profit_the_same_way_decide_does(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    knowledge, memory, kpis = _knowledge(tmp_path), _memory(tmp_path), _kpis(tmp_path)
    campaign_registry = _campaign_registry(tmp_path)
    knowledge.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))

    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=knowledge, memory=memory, kpis=kpis, registry=campaign_registry,
    )
    before = campaign.confidence_score

    goal = Goal(description="affiliate goal")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 200.0)
    kpis.record(f"cost_{goal.id}", 100.0)

    after = refresh_confidence(campaign.id, knowledge, memory, kpis, campaign_registry)

    assert after.confidence_score > before


# --- destination_url (2026-08-03, publish-readiness) ------------------------


def test_destination_url_defaults_to_blank_never_fabricated(tmp_path):
    campaign = Campaign(business_objective="a")

    assert campaign.destination_url == ""


def test_create_campaign_accepts_a_real_destination_url(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    campaign_registry = _campaign_registry(tmp_path)

    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=_knowledge(tmp_path), memory=_memory(tmp_path), kpis=_kpis(tmp_path),
        registry=campaign_registry, destination_url="https://example.com/track/real",
    )

    assert campaign.destination_url == "https://example.com/track/real"
    assert campaign_registry.get_campaign(campaign.id).destination_url == "https://example.com/track/real"


def test_success_law_ids_defaults_to_empty_never_fabricated(tmp_path):
    campaign = Campaign(business_objective="a")

    assert campaign.success_law_ids == []


def test_create_campaign_accepts_real_success_law_ids(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    campaign_registry = _campaign_registry(tmp_path)

    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=_knowledge(tmp_path), memory=_memory(tmp_path), kpis=_kpis(tmp_path),
        registry=campaign_registry, success_law_ids=["law-1", "law-2"],
    )

    assert campaign.success_law_ids == ["law-1", "law-2"]
    assert campaign_registry.get_campaign(campaign.id).success_law_ids == ["law-1", "law-2"]


def test_link_destination_url_attaches_a_real_url_to_an_existing_campaign(tmp_path):
    influencer_registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    campaign_registry = _campaign_registry(tmp_path)
    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=influencer_registry, knowledge=_knowledge(tmp_path), memory=_memory(tmp_path), kpis=_kpis(tmp_path),
        registry=campaign_registry,
    )
    assert campaign.destination_url == ""

    updated = link_destination_url(campaign.id, "https://example.com/track/real", campaign_registry)

    assert updated.destination_url == "https://example.com/track/real"
    assert campaign_registry.get_campaign(campaign.id).destination_url == "https://example.com/track/real"
