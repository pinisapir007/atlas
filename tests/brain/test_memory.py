import pytest

from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Proposal, StrategicObjective, Task


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


def test_completed_task_total_counts_completion_exactly_once(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="work")

    memory.save_task(task)
    assert memory.completed_task_total() == 0

    task.transition("done", "completed")
    memory.save_task(task)
    assert memory.completed_task_total() == 1

    # A normal later save of the same terminal Task must never double-count.
    memory.save_task(task)
    assert memory.completed_task_total() == 1


def test_completed_task_total_survives_task_archival(tmp_path):
    import json

    path = tmp_path / "brain.json"
    memory = BrainMemory(path)

    task = Task(goal_id="g1", description="work", status="done")
    memory.save_task(task)
    assert memory.completed_task_total() == 1

    # Simulate archival: historical Task leaves the live operational store,
    # while canonical lifetime metrics remain.
    raw = json.loads(path.read_text())
    raw["tasks"].pop(task.id)
    path.write_text(json.dumps(raw))

    reloaded = BrainMemory(path)
    assert reloaded.tasks() == []
    assert reloaded.completed_task_total() == 1


def test_old_brain_without_task_metrics_derives_initial_total(tmp_path):
    import json

    path = tmp_path / "brain.json"
    memory = BrainMemory(path)

    memory.save_task(Task(goal_id="g1", description="a", status="done"))
    memory.save_task(Task(goal_id="g1", description="b", status="done"))
    memory.save_task(Task(goal_id="g1", description="c", status="blocked"))

    raw = json.loads(path.read_text())
    del raw["task_metrics"]
    path.write_text(json.dumps(raw))

    assert BrainMemory(path).completed_task_total() == 2


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


def test_current_strategic_objective_is_none_before_any_is_set(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    assert memory.current_strategic_objective() is None
    assert memory.strategic_objectives() == []


def test_save_and_read_back_a_strategic_objective(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    objective = StrategicObjective(
        description="first $1,000", target_metric="revenue", target_value=1000.0,
        cash_flow_weight=0.9, strategic_value_weight=0.1,
    )
    memory.save_strategic_objective(objective)

    current = memory.current_strategic_objective()
    assert current.id == objective.id
    assert current.description == "first $1,000"
    assert memory.strategic_objectives() == [objective]


def test_current_strategic_objective_is_the_most_recently_created_one(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    first = StrategicObjective(
        description="first $1,000", target_metric="revenue", target_value=1000.0,
        cash_flow_weight=1.0, strategic_value_weight=0.0,
    )
    memory.save_strategic_objective(first)
    second = StrategicObjective(
        description="sustainable $10,000/month", target_metric="revenue", target_value=10000.0,
        cash_flow_weight=0.2, strategic_value_weight=0.8,
    )
    memory.save_strategic_objective(second)

    assert memory.current_strategic_objective().id == second.id
    assert len(memory.strategic_objectives()) == 2  # full history retained, nothing overwritten


def test_save_strategic_objective_rejects_weights_that_do_not_sum_to_one(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    bad = StrategicObjective(
        description="broken", target_metric="revenue", target_value=1000.0,
        cash_flow_weight=0.9, strategic_value_weight=0.9,
    )
    with pytest.raises(ValueError, match="must sum to 1.0"):
        memory.save_strategic_objective(bad)
    assert memory.current_strategic_objective() is None


def test_reads_a_real_brain_json_saved_before_strategic_objective_existed(tmp_path):
    # Tolerates a store saved before this key existed -- the same
    # no-migration-needed discipline knowledge.json's success_laws
    # addition already established.
    path = tmp_path / "brain.json"
    memory = BrainMemory(path)
    memory.save_goal(Goal(description="pre-existing goal"))

    import json

    raw = json.loads(path.read_text())
    del raw["strategic_objectives"]
    path.write_text(json.dumps(raw))

    memory2 = BrainMemory(path)
    assert memory2.current_strategic_objective() is None
    assert memory2.goals()[0].description == "pre-existing goal"
