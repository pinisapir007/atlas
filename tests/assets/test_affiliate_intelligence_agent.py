from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import AffiliateIntelligenceAgent
from atlas.assets.affiliate_intelligence.agents import DiscoveryAgent, RankingAgent, ResearchAgent
from atlas.brain.models import Task


def _agent(tmp_path):
    return AffiliateIntelligenceAgent(store=AffiliateStore(tmp_path / "affiliate_intelligence.json"))


def test_discovery_agent_creates_bare_opportunities_with_no_evaluation_data():
    opportunities = DiscoveryAgent().discover()

    assert len(opportunities) == 3
    for opportunity in opportunities:
        assert opportunity.stage == "discovered"
        assert opportunity.commission_per_conversion == 0.0
        assert opportunity.notes == ""


def test_research_agent_enriches_a_known_product():
    opportunity = DiscoveryAgent().discover()[0]
    enriched = ResearchAgent().enrich(opportunity)

    assert enriched.stage == "researched"
    assert enriched.commission_per_conversion > 0.0
    assert enriched.notes != ""
    assert "ResearchAgent" in enriched.history[-1]["reason"]


def test_ranking_agent_ranks_without_rejecting_anything():
    opportunities = [ResearchAgent().enrich(o) for o in DiscoveryAgent().discover()]
    ranked = RankingAgent().rank(opportunities)

    assert all(o.stage == "ranked" for o in ranked)
    scores = [o.score for o in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].product_name == "QuietDesk (ergonomic desk accessories)"  # highest score by design


def test_first_run_discovers_three_bare_opportunities(tmp_path):
    agent = _agent(tmp_path)

    result = agent.run()

    assert result["by_stage"]["discovered"] == 3


def test_run_with_task_stamps_goal_and_task_id(tmp_path):
    agent = _agent(tmp_path)
    task = Task(goal_id="goal-a", description="discover")

    result = agent.run(task=task)

    assert all(o["goal_id"] == "goal-a" for o in result["opportunities"])


def test_second_run_researches_all_discovered_opportunities(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discover
    result = agent.run()  # research

    assert result["by_stage"]["researched"] == 3
    assert all(o["notes"] for o in result["opportunities"])


def test_third_run_ranks_all_researched_opportunities(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discover
    agent.run()  # research
    result = agent.run()  # rank

    assert result["by_stage"]["ranked"] == 3
    report = result["ranked_report"]
    assert [entry["rank"] for entry in report] == [1, 2, 3]
    assert report[0]["product_name"] == "QuietDesk (ergonomic desk accessories)"
    assert report[0]["score"] > report[1]["score"] > report[2]["score"]


def test_intake_real_product_seeds_a_ranked_opportunity_with_the_real_link(tmp_path):
    agent = _agent(tmp_path)

    opportunity = agent.intake_real_product(
        goal_id="goal-a",
        product_name="Real Program",
        description="A real, signed-up affiliate program",
        category="software",
        commission_per_conversion=30.0,
        real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        provider="digistore24",
        provider_product_id="123456",
        estimated_conversion=0.02,
    )

    assert opportunity.stage == "ranked"
    assert opportunity.goal_id == "goal-a"
    assert opportunity.real_affiliate_link == "https://www.digistore24.com/redir/123456/myaffid/"
    assert opportunity.provider == "digistore24"
    assert opportunity.provider_product_id == "123456"
    assert opportunity.score > 0.0  # computed via score_opportunity(), not left at 0.0


def test_intake_real_product_is_not_touched_by_placeholder_discovery_research_or_ranking(tmp_path):
    agent = _agent(tmp_path)
    agent.intake_real_product(
        goal_id="goal-a",
        product_name="Real Program",
        description="A real, signed-up affiliate program",
        category="software",
        commission_per_conversion=30.0,
        real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        provider="digistore24",
    )

    result = agent.run()  # store isn't empty, and nothing is 'discovered'/'researched' -- a safe no-op

    assert sum(result["by_stage"].values()) == 1
    assert result["opportunities"][0]["product_name"] == "Real Program"
    assert result["opportunities"][0]["stage"] == "ranked"


def test_founder_choice_dispatch_marks_the_real_opportunity_selected_for_marketing(tmp_path):
    agent = _agent(tmp_path)
    opportunity = agent.intake_real_product(
        goal_id="goal-a",
        product_name="Real Program",
        description="A real, signed-up affiliate program",
        category="software",
        commission_per_conversion=30.0,
        real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        provider="digistore24",
    )
    choice_task = Task(
        goal_id="goal-a", description="choose it", category="affiliate_intelligence",
        reversible=False, source_opportunity_id=opportunity.id,
    )

    result = agent.run(task=choice_task)

    chosen = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert chosen["stage"] == "selected_for_marketing"


def test_mismatched_category_task_is_a_safe_no_op(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discover, so there's state to (not) mutate
    unrelated_task = Task(goal_id="goal-a", description="unrelated", category="general")

    result = agent.run(task=unrelated_task)

    assert result["by_stage"]["discovered"] == 3  # unchanged, not advanced to researched


def test_report_does_not_mutate_state(tmp_path):
    agent = _agent(tmp_path)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after


def test_flag_off_first_run_still_discovers_placeholders_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", raising=False)
    agent = _agent(tmp_path)

    result = agent.run()

    assert result["by_stage"]["discovered"] == 3
    assert "message" not in result


def test_flag_on_empty_store_never_fabricates_placeholders(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    agent = _agent(tmp_path)

    result = agent.run()

    assert result["opportunities"] == []
    assert sum(result["by_stage"].values()) == 0


def test_flag_on_empty_store_reports_no_real_opportunity_found(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    agent = _agent(tmp_path)

    result = agent.run()

    assert result["message"] == "No real opportunity found."
    assert agent.report()["message"] == "No real opportunity found."


def test_flag_on_with_a_real_opportunity_present_reports_no_message(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    agent = _agent(tmp_path)
    agent.intake_real_product(
        goal_id="goal-a",
        product_name="Real Program",
        description="A real, signed-up affiliate program",
        category="software",
        commission_per_conversion=30.0,
        real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        provider="digistore24",
    )

    result = agent.run()

    assert "message" not in result


def test_flag_on_never_advances_stuck_at_empty_across_repeated_ticks(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    agent = _agent(tmp_path)

    agent.run()
    result = agent.run()

    assert result["opportunities"] == []
    assert result["message"] == "No real opportunity found."
