from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, StrategicObjective
from atlas.brain.strategist import SimpleStrategist


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def test_goals_with_no_input_are_skipped(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="no data at all")

    decisions = SimpleStrategist().reallocate([goal], kpis, [])

    assert decisions == []


def test_ranks_short_horizon_by_cash_flow_score(tmp_path):
    kpis = _kpis(tmp_path)
    strong = Goal(description="strong", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak", founder_estimate={"expected_revenue": 100.0})

    decisions = {d["goal_id"]: d for d in SimpleStrategist().reallocate([strong, weak], kpis, [])}

    assert decisions[strong.id]["new_priority"] == 1
    assert decisions[weak.id]["new_priority"] == 2
    assert decisions[strong.id]["horizon"] == "short"


def test_ranks_long_horizon_by_strategic_value_not_cash_flow(tmp_path):
    kpis = _kpis(tmp_path)
    visionary = Goal(
        description="visionary, no near-term cash",
        horizon="long",
        founder_estimate={"expected_revenue": 0.0, "long_term_strategic_value": 0.9, "scalability": 0.9},
    )
    cash_grab = Goal(
        description="fast cash, no lasting value",
        horizon="long",
        founder_estimate={"expected_revenue": 5000.0, "long_term_strategic_value": 0.1, "scalability": 0.1},
    )

    decisions = {d["goal_id"]: d for d in SimpleStrategist().reallocate([visionary, cash_grab], kpis, [])}

    assert decisions[visionary.id]["new_priority"] == 1
    assert decisions[cash_grab.id]["new_priority"] == 2


def test_no_decision_when_nothing_changes(tmp_path):
    kpis = _kpis(tmp_path)
    strong = Goal(description="strong", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak", founder_estimate={"expected_revenue": 100.0})
    strategist = SimpleStrategist()

    first_pass = strategist.reallocate([strong, weak], kpis, [])
    for decision in first_pass:
        goal = strong if decision["goal_id"] == strong.id else weak
        goal.priority = decision["new_priority"]
        goal.status = decision["new_status"]

    second_pass = strategist.reallocate([strong, weak], kpis, [])

    assert second_pass == []


def test_pause_when_bottom_and_revenue_stagnant(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    strong = Goal(description="strong", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak", founder_estimate={"expected_revenue": 100.0})
    for value in (50.0, 50.0, 50.0):
        kpis.record(f"revenue_{weak.id}", value)

    decisions = {d["goal_id"]: d for d in SimpleStrategist().reallocate([strong, weak], kpis, [])}

    assert decisions[weak.id]["new_status"] == "paused"
    assert decisions[strong.id]["new_status"] == "active"


def test_no_pause_without_enough_kpi_history(tmp_path):
    kpis = _kpis(tmp_path)
    strong = Goal(description="strong", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak", founder_estimate={"expected_revenue": 100.0})

    decisions = {d["goal_id"]: d for d in SimpleStrategist().reallocate([strong, weak], kpis, [])}

    assert decisions[weak.id]["new_status"] == "active"
    assert decisions[weak.id]["new_priority"] == 2


def test_single_goal_bucket_never_pauses(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    goal = Goal(description="only one", founder_estimate={"expected_revenue": 500.0})
    for value in (10.0, 10.0, 10.0):
        kpis.record(f"revenue_{goal.id}", value)

    decisions = SimpleStrategist().reallocate([goal], kpis, [])

    assert len(decisions) == 1
    assert decisions[0]["new_status"] == "active"
    assert decisions[0]["new_priority"] == 1


def test_paused_goals_excluded_from_scoring(tmp_path):
    kpis = _kpis(tmp_path)
    active_a = Goal(description="a", founder_estimate={"expected_revenue": 1000.0})
    already_paused = Goal(
        description="paused",
        status="paused",
        founder_estimate={"expected_revenue": 50000.0},
    )
    active_b = Goal(description="b", founder_estimate={"expected_revenue": 100.0})

    decisions = {d["goal_id"]: d for d in SimpleStrategist().reallocate([active_a, already_paused, active_b], kpis, [])}

    assert already_paused.id not in decisions
    assert decisions[active_a.id]["bucket_size"] == 2
    assert decisions[active_a.id]["new_priority"] == 1
    assert decisions[active_b.id]["new_priority"] == 2


def test_the_same_two_goals_rank_differently_under_two_different_real_objectives(tmp_path):
    # The real M2 success criterion: identical founder_estimate on both
    # goals, yet the real, current StrategicObjective alone flips which
    # one ranks first -- proof the company's current phase actually
    # reweights the decision, not just documents it.
    kpis = _kpis(tmp_path)
    fast_cash_no_future = Goal(
        description="fast cash, no lasting value",
        horizon="short",
        founder_estimate={
            "expected_revenue": 5000.0, "required_investment": 100.0, "time_to_first_profit": 3.0,
            "scalability": 0.0, "automation_potential": 0.0, "long_term_strategic_value": 0.0,
        },
    )
    slow_but_scalable = Goal(
        description="slow now, scalable later",
        horizon="short",
        founder_estimate={
            "expected_revenue": 100.0, "required_investment": 5000.0, "time_to_first_profit": 180.0,
            "scalability": 1.0, "automation_potential": 1.0, "long_term_strategic_value": 1.0,
        },
    )

    first_dollar_objective = StrategicObjective(
        description="first $1,000, fastest and safest", target_metric="revenue", target_value=1000.0,
        cash_flow_weight=1.0, strategic_value_weight=0.0,
    )
    decisions_survival = {
        d["goal_id"]: d
        for d in SimpleStrategist().reallocate([fast_cash_no_future, slow_but_scalable], kpis, [], objective=first_dollar_objective)
    }
    assert decisions_survival[fast_cash_no_future.id]["new_priority"] == 1
    assert decisions_survival[slow_but_scalable.id]["new_priority"] == 2

    scale_objective = StrategicObjective(
        description="sustainable $10,000/month", target_metric="revenue", target_value=10000.0,
        cash_flow_weight=0.0, strategic_value_weight=1.0,
    )
    decisions_scale = {
        d["goal_id"]: d
        for d in SimpleStrategist().reallocate([fast_cash_no_future, slow_but_scalable], kpis, [], objective=scale_objective)
    }
    assert decisions_scale[slow_but_scalable.id]["new_priority"] == 1
    assert decisions_scale[fast_cash_no_future.id]["new_priority"] == 2


def test_reallocate_still_defaults_to_the_legacy_rule_when_no_objective_is_passed(tmp_path):
    kpis = _kpis(tmp_path)
    strong = Goal(description="strong", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak", founder_estimate={"expected_revenue": 100.0})

    decisions = {d["goal_id"]: d for d in SimpleStrategist().reallocate([strong, weak], kpis, [])}

    assert decisions[strong.id]["objective_id"] is None
    assert "no strategic objective set" in decisions[strong.id]["reason"]
