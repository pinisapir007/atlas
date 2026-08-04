from datetime import datetime, timedelta, timezone

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, SuccessLaw
from atlas.brain.reporter import Reporter
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry


def test_reallocations_within_period_are_included(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(description="grow")
    memory.save_goal(goal)
    memory.append_log(
        {
            "kind": "reallocation",
            "goal_id": goal.id,
            "horizon": "short",
            "old_priority": 3,
            "new_priority": 1,
            "old_status": "active",
            "new_status": "active",
            "reason": "ranked 1/2 in short-horizon cohort",
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )

    report = Reporter().summarize("daily", memory, KPIRegistry(memory))

    assert len(report["reallocations"]) == 1
    entry = report["reallocations"][0]
    assert entry["goal_id"] == goal.id
    assert entry["description"] == "grow"
    assert entry["new_priority"] == 1


def test_reallocations_outside_period_are_excluded(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(description="grow")
    memory.save_goal(goal)
    old_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    memory.append_log({"kind": "reallocation", "goal_id": goal.id, "new_priority": 1, "at": old_at})

    report = Reporter().summarize("daily", memory, KPIRegistry(memory))

    assert report["reallocations"] == []


def test_non_reallocation_log_entries_are_ignored(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.append_log({"event": "something else", "at": datetime.now(timezone.utc).isoformat()})

    report = Reporter().summarize("daily", memory, KPIRegistry(memory))

    assert report["reallocations"] == []


def test_cash_flow_includes_goals_with_revenue_or_cost_measured(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(description="grow")
    memory.save_goal(goal)
    kpis = KPIRegistry(memory)
    kpis.record(f"revenue_{goal.id}", 1000.0)
    kpis.record(f"cost_{goal.id}", 400.0)

    report = Reporter().summarize("daily", memory, kpis)

    assert len(report["cash_flow"]) == 1
    entry = report["cash_flow"][0]
    assert entry["goal_id"] == goal.id
    assert entry["revenue"] == 1000.0
    assert entry["cost"] == 400.0
    assert entry["profit"] == 600.0
    assert entry["roi"] == 1.5


def test_cash_flow_excludes_goals_with_no_revenue_or_cost(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="not yet measured"))

    report = Reporter().summarize("daily", memory, KPIRegistry(memory))

    assert report["cash_flow"] == []


def test_cash_flow_includes_partial_data_with_none_profit(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(description="revenue only, no cost tracked yet")
    memory.save_goal(goal)
    kpis = KPIRegistry(memory)
    kpis.record(f"revenue_{goal.id}", 500.0)

    report = Reporter().summarize("daily", memory, kpis)

    assert len(report["cash_flow"]) == 1
    entry = report["cash_flow"][0]
    assert entry["revenue"] == 500.0
    assert entry["cost"] is None
    assert entry["profit"] is None
    assert entry["roi"] is None


def test_new_sections_default_to_empty_when_registries_are_not_provided(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")

    report = Reporter().summarize("daily", memory, KPIRegistry(memory))

    assert report["opportunities"] == {"findings_this_period": 0, "categories_ranked": []}
    assert report["success_laws"] == {"total": 0, "evidence_backed": 0, "ranked_by_track_record": []}
    assert report["asset_portfolio"] == []
    assert report["publishing_readiness"] == {"packages_ready": 0, "steps_blocked": []}


def test_opportunities_section_reflects_real_ranked_evidence(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    knowledge.save_finding(Finding(source="a", category="affiliate", description="d1", evidence="https://e1", subject="KetoDNA", market="US"))
    knowledge.save_finding(Finding(source="b", category="affiliate", description="d2", evidence="https://e2", subject="KetoDNA", market="US"))

    report = Reporter().summarize("daily", memory, KPIRegistry(memory), knowledge=knowledge)

    assert report["opportunities"]["findings_this_period"] == 2
    entry = report["opportunities"]["categories_ranked"][0]
    assert entry["category"] == "affiliate"
    assert entry["top_subject"] == "KetoDNA"
    assert entry["recommended_market"] == "US"


def test_success_laws_section_reports_real_track_record(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    campaigns = CampaignRegistry(tmp_path / "campaigns.json")
    law = SuccessLaw(principle="Bundle urgency with the CTA", source_description="https://case-study")
    knowledge.save_success_law(law)

    report = Reporter().summarize("daily", memory, KPIRegistry(memory), knowledge=knowledge, campaigns=campaigns)

    assert report["success_laws"]["total"] == 1
    assert report["success_laws"]["evidence_backed"] == 0
    entry = report["success_laws"]["ranked_by_track_record"][0]
    assert entry["principle"] == "Bundle urgency with the CTA"
    assert entry["real_track_record"] is None  # no measured campaigns yet -- never fabricated


def test_asset_portfolio_section_lists_real_active_assets(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    campaigns = CampaignRegistry(tmp_path / "campaigns.json")
    influencers = InfluencerRegistry(tmp_path / "influencers.json")
    brands = BrandRegistry(tmp_path / "brands.json")
    influencers.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["affiliate"]))

    report = Reporter().summarize(
        "daily", memory, KPIRegistry(memory), campaigns=campaigns, influencers=influencers, brands=brands
    )

    assert len(report["asset_portfolio"]) == 1
    assert report["asset_portfolio"][0]["name"] == "Mira"


def test_publishing_readiness_section_reflects_real_execution_plan_steps(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    execution_plans = ExecutionPlanRegistry(tmp_path / "execution_plans.json")

    report = Reporter().summarize("daily", memory, KPIRegistry(memory), execution_plans=execution_plans)

    assert report["publishing_readiness"] == {"packages_ready": 0, "steps_blocked": []}
