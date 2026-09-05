from atlas.assets.affiliate_department.agent import AffiliateDepartmentAgent
from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.scoring import score_opportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.models import Task


def _agent(tmp_path):
    return AffiliateDepartmentAgent(
        store=AffiliateStore(tmp_path / "affiliate_department.json"),
        allow_placeholder_discovery=True,
    )


def test_default_run_never_discovers_placeholder_opportunities(tmp_path):
    agent = AffiliateDepartmentAgent(
        store=AffiliateStore(tmp_path / "affiliate_department.json")
    )

    result = agent.run()

    assert result["opportunities"] == []
    assert sum(result["by_stage"].values()) == 0


def test_first_run_discovers_three_placeholder_opportunities(tmp_path):
    agent = _agent(tmp_path)

    result = agent.run()

    assert result["status"] == "done"
    assert result["by_stage"]["discovered"] == 3
    assert sum(result["by_stage"].values()) == 3


def test_run_with_task_stamps_opportunities_with_goal_and_task_id(tmp_path):
    agent = _agent(tmp_path)
    task = Task(goal_id="goal-a", description="discover affiliate opportunities")

    result = agent.run(task=task)

    assert all(o["goal_id"] == "goal-a" for o in result["opportunities"])
    assert all(o["task_id"] == task.id for o in result["opportunities"])


def test_run_without_task_leaves_goal_and_task_id_none(tmp_path):
    agent = _agent(tmp_path)

    result = agent.run()

    assert all(o["goal_id"] is None for o in result["opportunities"])


def test_second_run_evaluates_selects_best_and_rejects_others(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discover
    result = agent.run()  # evaluate

    by_stage = result["by_stage"]
    assert by_stage["selected"] == 1
    assert by_stage["lost"] == 2

    selected = next(o for o in result["opportunities"] if o["stage"] == "selected")
    assert selected["product_name"] == "QuietDesk (ergonomic desk accessories)"  # highest score by design
    assert "highest score" in selected["history"][-1]["reason"]

    for opportunity in result["opportunities"]:
        if opportunity["stage"] == "lost":
            assert "below selected candidate's" in opportunity["history"][-1]["reason"]


def test_third_run_plans_content_only_for_the_selected_opportunity(tmp_path):
    agent = _agent(tmp_path)
    agent.run()  # discover
    agent.run()  # evaluate
    result = agent.run()  # plan content

    by_stage = result["by_stage"]
    assert by_stage["content_planned"] == 1
    assert by_stage["lost"] == 2

    planned = next(o for o in result["opportunities"] if o["stage"] == "content_planned")
    brief = planned["content_brief"]
    assert set(brief.keys()) == {"audience", "hook", "headline", "cta", "platform", "content_ideas"}
    assert len(brief["content_ideas"]) == 3
    assert "not published" in planned["history"][-1]["reason"]


def test_report_does_not_mutate_state(tmp_path):
    agent = _agent(tmp_path)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after


def test_further_runs_are_stable_once_content_planned(tmp_path):
    agent = _agent(tmp_path)
    agent.run()
    agent.run()
    agent.run()

    stable = agent.run()

    assert stable["by_stage"]["content_planned"] == 1
    assert stable["by_stage"]["lost"] == 2


def test_score_opportunity_rewards_conversion_and_commission_penalizes_competition_and_difficulty():
    strong = AffiliateOpportunity(
        product_name="strong",
        description="",
        commission_per_conversion=25.0,
        estimated_conversion=0.05,
        competition=0.2,
        content_difficulty=0.2,
    )
    weak = AffiliateOpportunity(
        product_name="weak",
        description="",
        commission_per_conversion=15.0,
        estimated_conversion=0.01,
        competition=0.8,
        content_difficulty=0.7,
    )

    assert score_opportunity(strong) > score_opportunity(weak)


def test_score_opportunity_is_zero_at_maximum_competition():
    maxed_out = AffiliateOpportunity(
        product_name="x",
        description="",
        commission_per_conversion=100.0,
        estimated_conversion=1.0,
        competition=1.0,
        content_difficulty=0.0,
    )
    assert score_opportunity(maxed_out) == 0.0
