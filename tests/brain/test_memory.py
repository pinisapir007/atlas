import pytest

from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Proposal, Task


class InMemoryBrainStore:
    """A minimal fake BrainStore — proves BrainMemory's persistence is
    genuinely swappable, not just delegated to another JSON file."""

    def __init__(self):
        self.data = None
        self.write_count = 0

    def read(self):
        return self.data

    def write(self, data):
        self.data = data
        self.write_count += 1


def test_round_trips_goals_tasks_proposals_and_log(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(description="grow revenue", priority=1)
    memory.save_goal(goal)

    task = Task(goal_id=goal.id, description="do work")
    memory.save_task(task)

    proposal = Proposal(task_id=task.id, kind="redesign", rationale="evidence-backed")
    memory.save_proposal(proposal)

    memory.append_log({"event": "test"})
    memory.record_kpi("revenue", 100.0, "2026-01-01T00:00:00+00:00")

    reloaded = BrainMemory(tmp_path / "brain.json")
    assert reloaded.get_goal(goal.id).description == "grow revenue"
    assert reloaded.get_task(task.id).description == "do work"
    assert reloaded.get_proposal(proposal.id).kind == "redesign"
    assert reloaded.log() == [{"event": "test"}]
    assert reloaded.kpi_history("revenue")[0]["value"] == 100.0


def test_goal_round_trip_preserves_founder_estimate_and_horizon(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(
        description="low-ticket offer",
        horizon="long",
        founder_estimate={"expected_revenue": 500.0, "scalability": 0.8},
    )
    memory.save_goal(goal)

    reloaded = BrainMemory(tmp_path / "brain.json").get_goal(goal.id)

    assert reloaded.horizon == "long"
    assert reloaded.founder_estimate == {"expected_revenue": 500.0, "scalability": 0.8}


def test_goal_defaults_stay_backward_compatible(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    goal = Goal(description="plain goal")
    memory.save_goal(goal)

    reloaded = BrainMemory(tmp_path / "brain.json").get_goal(goal.id)

    assert reloaded.horizon == "short"
    assert reloaded.founder_estimate == {}
    assert reloaded.engine_id is None


def test_missing_goal_raises_keyerror(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    with pytest.raises(KeyError):
        memory.get_goal("does-not-exist")


def test_missing_task_raises_keyerror(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    with pytest.raises(KeyError):
        memory.get_task("does-not-exist")


def test_accepts_an_injected_store_instead_of_a_path():
    store = InMemoryBrainStore()
    memory = BrainMemory(store=store)

    goal = Goal(description="grow revenue", priority=1)
    memory.save_goal(goal)

    assert store.write_count == 1
    assert memory.get_goal(goal.id).description == "grow revenue"
    # A second BrainMemory over the same store sees the same state — proves
    # the store, not a path, is the actual source of truth.
    assert BrainMemory(store=store).get_goal(goal.id).description == "grow revenue"


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "brain.json"
    memory = BrainMemory(path)
    memory.save_goal(Goal(description="grow revenue"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
