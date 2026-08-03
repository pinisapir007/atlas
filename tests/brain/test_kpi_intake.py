from atlas.brain.kpi import KPIRegistry
from atlas.brain.kpi_intake import record_manual_cost, record_manual_revenue, record_revenue
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def _won_opportunity(goal_id, revenue, profit, opp_id="opp-1"):
    return {
        "id": opp_id,
        "stage": "won",
        "goal_id": goal_id,
        "recurring_monthly_revenue": revenue,
        "estimated_gross_profit": profit,
    }


def test_revenue_shape_accumulates_onto_running_total(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="promote")

    record_revenue(task, {"status": "done", "channel": "affiliate", "revenue_generated": 100.0}, kpis)
    record_revenue(task, {"status": "done", "channel": "affiliate", "revenue_generated": 50.0}, kpis)

    assert kpis.latest("revenue_goal-a") == 150.0


def test_recruitment_shape_attributes_via_opportunity_goal_id_not_task(tmp_path):
    kpis = _kpis(tmp_path)
    # The dispatching task belongs to goal-b, but the won opportunity is
    # tagged goal-a — attribution must follow the opportunity, not the task.
    triggering_task = Task(goal_id="goal-b", description="dispatch that happens to run the pipeline")
    result = {"status": "done", "opportunities": [_won_opportunity("goal-a", 1000.0, 400.0)]}

    record_revenue(triggering_task, result, kpis)

    assert kpis.latest("revenue_goal-a") == 1000.0
    assert kpis.latest("cost_goal-a") == 600.0
    assert kpis.latest("revenue_goal-b") is None
    assert kpis.latest("cost_goal-b") is None


def test_untagged_opportunity_contributes_to_no_goal(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    result = {"status": "done", "opportunities": [_won_opportunity(None, 1000.0, 400.0)]}

    record_revenue(task, result, kpis)

    assert kpis.latest("revenue_goal-a") is None
    assert kpis.names() == []


def test_non_won_opportunities_are_excluded_even_with_valid_goal_id(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    pipeline_stage_opp = {
        "id": "opp-1",
        "stage": "proposal_ready",
        "goal_id": "goal-a",
        "recurring_monthly_revenue": 5000.0,
        "estimated_gross_profit": 2000.0,
    }

    record_revenue(task, {"status": "done", "opportunities": [pipeline_stage_opp]}, kpis)

    assert kpis.latest("revenue_goal-a") is None


def test_repeated_identical_recruitment_dispatch_is_idempotent(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    result = {"status": "done", "opportunities": [_won_opportunity("goal-a", 1000.0, 400.0)]}

    record_revenue(task, result, kpis)
    record_revenue(task, result, kpis)
    record_revenue(task, result, kpis)

    assert kpis.latest("revenue_goal-a") == 1000.0
    assert kpis.latest("cost_goal-a") == 600.0
    assert len(kpis.history("revenue_goal-a")) == 3  # recorded each time, never inflated


def test_recruitment_totals_sum_multiple_won_opportunities_for_the_same_goal(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    result = {
        "status": "done",
        "opportunities": [
            _won_opportunity("goal-a", 1000.0, 400.0, opp_id="opp-1"),
            _won_opportunity("goal-a", 500.0, 300.0, opp_id="opp-2"),
        ],
    }

    record_revenue(task, result, kpis)

    assert kpis.latest("revenue_goal-a") == 1500.0
    assert kpis.latest("cost_goal-a") == (1000.0 - 400.0) + (500.0 - 300.0)


def test_record_manual_revenue_accumulates_revenue_and_cost(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_revenue("goal-a", 100.0, 30.0, kpis)
    record_manual_revenue("goal-a", 50.0, 10.0, kpis)

    assert kpis.latest("revenue_goal-a") == 150.0
    assert kpis.latest("cost_goal-a") == 40.0


def test_record_manual_revenue_without_cost_leaves_cost_untouched(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_revenue("goal-a", 100.0, None, kpis)

    assert kpis.latest("revenue_goal-a") == 100.0
    assert kpis.latest("cost_goal-a") is None


def test_record_manual_cost_accumulates_without_touching_revenue(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_cost("goal-a", 30.0, kpis)
    record_manual_cost("goal-a", 10.0, kpis)

    assert kpis.latest("cost_goal-a") == 40.0
    assert kpis.latest("revenue_goal-a") is None


def test_unrecognized_shape_records_nothing(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")

    record_revenue(task, {"status": "done", "opportunities": [{"description": "x", "suggested_category": "y"}]}, kpis)
    record_revenue(task, {"status": "done"}, kpis)
    record_revenue(task, None, kpis)
    record_revenue(task, "not a dict", kpis)

    assert kpis.names() == []
