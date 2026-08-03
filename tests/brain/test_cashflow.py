from atlas.brain.cashflow import goal_cash_flow, profit, roi
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal


def _kpis(tmp_path):
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def test_profit_is_revenue_minus_cost_when_both_measured(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 1000.0)
    kpis.record(f"cost_{goal.id}", 400.0)

    assert profit(goal, kpis) == 600.0


def test_profit_is_none_when_cost_unmeasured(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 1000.0)

    assert profit(goal, kpis) is None


def test_profit_is_none_when_revenue_unmeasured(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"cost_{goal.id}", 400.0)

    assert profit(goal, kpis) is None


def test_profit_uses_latest_reading_not_a_sum_of_history(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 500.0)
    kpis.record(f"revenue_{goal.id}", 1000.0)
    kpis.record(f"cost_{goal.id}", 400.0)

    assert profit(goal, kpis) == 600.0


def test_roi_is_profit_over_cost(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 1000.0)
    kpis.record(f"cost_{goal.id}", 400.0)

    assert roi(goal, kpis) == 1.5


def test_roi_is_none_when_cost_is_zero(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 1000.0)
    kpis.record(f"cost_{goal.id}", 0.0)

    assert roi(goal, kpis) is None


def test_roi_is_none_when_unmeasured(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")

    assert roi(goal, kpis) is None


def test_roi_can_be_negative_when_cost_exceeds_revenue(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"cost_{goal.id}", 400.0)

    assert roi(goal, kpis) == -0.75


def test_goal_cash_flow_includes_settled_alongside_claimed_revenue(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 1000.0)
    kpis.record(f"settled_{goal.id}", 600.0)

    entry = goal_cash_flow([goal], kpis)[0]
    assert entry["revenue"] == 1000.0
    assert entry["settled"] == 600.0


def test_goal_cash_flow_includes_a_goal_with_only_settlement_measured(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"settled_{goal.id}", 100.0)

    entries = goal_cash_flow([goal], kpis)
    assert len(entries) == 1
    assert entries[0]["revenue"] is None
    assert entries[0]["settled"] == 100.0
