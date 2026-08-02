import pytest

from atlas.assets.recruitment_workforce.agent import RecruitmentAgent
from atlas.assets.recruitment_workforce.store import WorkforceStore
from atlas.brain.models import Task


def _agent(tmp_path):
    return RecruitmentAgent(store=WorkforceStore(tmp_path / "recruitment_workforce.json"))


def test_first_run_seeds_and_creates_a_discovered_opportunity(tmp_path):
    agent = _agent(tmp_path)

    result = agent.run()

    assert result["status"] == "done"
    assert result["by_stage"]["discovered"] == 1
    assert sum(result["by_stage"].values()) == 1


def test_opportunity_advances_through_qualified_and_matched_with_revenue_model(tmp_path):
    agent = _agent(tmp_path)

    agent.run()  # discovered (seeded)
    agent.run()  # qualified
    result = agent.run()  # matched: candidates attached, revenue model computed

    opp = result["opportunities"][0]
    assert opp["stage"] == "matched"
    assert len(opp["candidate_ids"]) == 3
    assert opp["fee_per_hour"] == 28.0
    assert opp["recurring_monthly_revenue"] > 0
    assert opp["estimated_gross_profit"] > 0
    assert opp["placement_fee"] > 0


def test_matching_blocks_when_not_enough_available_workforce(tmp_path):
    agent = _agent(tmp_path)
    agent.intake_demand(
        industry="healthcare", employer_name="Clinic", role="Nurse", headcount=2, rate_expectation_per_hour=50.0
    )
    agent.intake_candidate(industry="healthcare", description="Nurse A", pay_rate_expectation_per_hour=35.0)

    agent.run()  # discovered
    agent.run()  # qualified
    result = agent.run()  # attempt match: only 1 of 2 needed -> stays qualified

    opp = next(o for o in result["opportunities"] if o["industry"] == "healthcare")
    assert opp["stage"] == "qualified"


def test_proposal_ready_requires_founder_approval_to_reach_active(tmp_path):
    agent = _agent(tmp_path)
    for _ in range(4):
        agent.run()  # discovered -> qualified -> matched -> proposal_ready

    opp = agent.report()["opportunities"][0]
    assert opp["stage"] == "proposal_ready"

    stuck = agent.run()  # further ticks do NOT auto-advance past the gate
    assert stuck["opportunities"][0]["stage"] == "proposal_ready"

    agent.approve_outreach(opp["id"])
    approved = agent.report()
    assert approved["opportunities"][0]["stage"] == "active"


def test_active_requires_founder_approval_to_reach_won(tmp_path):
    agent = _agent(tmp_path)
    for _ in range(4):
        agent.run()
    opp_id = agent.report()["opportunities"][0]["id"]
    agent.approve_outreach(opp_id)

    stuck = agent.run()
    assert stuck["opportunities"][0]["stage"] == "active"

    agent.approve_commitment(opp_id)
    won = agent.report()
    assert won["opportunities"][0]["stage"] == "won"
    assert won["total_won_recurring_monthly_revenue"] > 0
    assert won["total_won_estimated_gross_profit"] > 0


def test_approve_outreach_rejects_wrong_stage(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discovered
    opp_id = agent.report()["opportunities"][0]["id"]

    with pytest.raises(ValueError):
        agent.approve_outreach(opp_id)


def test_approve_commitment_rejects_wrong_stage(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discovered
    opp_id = agent.report()["opportunities"][0]["id"]

    with pytest.raises(ValueError):
        agent.approve_commitment(opp_id)


def test_mark_lost_is_terminal(tmp_path):
    agent = _agent(tmp_path)
    agent.run()
    opp_id = agent.report()["opportunities"][0]["id"]

    lost = agent.mark_lost(opp_id, reason="employer went with a competitor")

    assert lost.stage == "lost"
    with pytest.raises(ValueError):
        agent.mark_lost(opp_id)


def test_report_does_not_mutate_state(tmp_path):
    agent = _agent(tmp_path)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after


def test_run_with_task_stamps_new_opportunities_with_goal_and_task_id(tmp_path):
    agent = _agent(tmp_path)
    task = Task(goal_id="goal-a", description="run recruitment engine")

    result = agent.run(task=task)

    opp = result["opportunities"][0]
    assert opp["goal_id"] == "goal-a"
    assert opp["task_id"] == task.id


def test_run_without_task_leaves_goal_and_task_id_none(tmp_path):
    agent = _agent(tmp_path)

    result = agent.run()

    opp = result["opportunities"][0]
    assert opp["goal_id"] is None
    assert opp["task_id"] is None


def test_advancing_opportunity_never_overwrites_original_attribution(tmp_path):
    agent = _agent(tmp_path)
    creating_task = Task(goal_id="goal-a", description="run recruitment engine")
    agent.run(task=creating_task)  # creates + stamps the opportunity (discovered)

    other_goal_task = Task(goal_id="goal-b", description="a different goal's dispatch")
    result = agent.run(task=other_goal_task)  # only advances the existing opportunity

    opp = result["opportunities"][0]
    assert opp["goal_id"] == "goal-a"
    assert opp["task_id"] == creating_task.id


def test_reusable_across_industries_via_manual_intake(tmp_path):
    agent = _agent(tmp_path)
    # Real intake data (not the placeholder seed) for a different industry
    agent.intake_demand(
        industry="construction", employer_name="BuildCo", role="Laborer", headcount=1, rate_expectation_per_hour=40.0
    )
    agent.intake_candidate(industry="construction", description="Laborer A", pay_rate_expectation_per_hour=25.0)

    result = agent.run()

    industries = {o["industry"] for o in result["opportunities"]}
    assert "construction" in industries
    assert "warehouse_logistics" not in industries  # placeholder seed never triggered
