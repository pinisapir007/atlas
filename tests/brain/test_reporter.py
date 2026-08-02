from datetime import datetime, timedelta, timezone

from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal
from atlas.brain.reporter import Reporter


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
