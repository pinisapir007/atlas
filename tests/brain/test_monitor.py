from pathlib import Path

from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.monitor import Monitor
from atlas.core.loader import discover_manifests
from atlas.core.registry import Registry
from atlas.core.store import JSONStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "assets"


def _registry(tmp_path):
    return Registry(discover_manifests([FIXTURES]), store=JSONStore(tmp_path / "state.json"))


def test_sync_marks_delegated_task_done_via_report(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    task = Task(
        goal_id="g1",
        description="work",
        assigned_asset_id="sample-triggerable",
        status="delegated",
    )
    memory.save_task(task)

    Monitor().sync([task], registry, memory, kpis)

    assert task.status == "done"
    assert memory.get_task(task.id).status == "done"


def test_sync_records_completed_simple_planner_fingerprint_on_goal(tmp_path):
    from atlas.brain.models import Goal

    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    goal = Goal(description="Grow revenue", priority=1)
    memory.save_goal(goal)

    task = Task(
        goal_id=goal.id,
        description="Advance goal: Grow revenue",
        assigned_asset_id="sample-triggerable",
        status="delegated",
    )
    memory.save_task(task)

    Monitor().sync([task], registry, memory, kpis)

    saved_goal = memory.get_goal(goal.id)
    assert saved_goal.planner_completion_fingerprint == "Advance goal: Grow revenue"


def test_sync_does_not_record_unrelated_done_task_as_planner_completion(tmp_path):
    from atlas.brain.models import Goal

    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    goal = Goal(description="Grow revenue", priority=1)
    memory.save_goal(goal)

    task = Task(
        goal_id=goal.id,
        description="Analyze last campaign",
        assigned_asset_id="sample-triggerable",
        status="delegated",
    )
    memory.save_task(task)

    Monitor().sync([task], registry, memory, kpis)

    saved_goal = memory.get_goal(goal.id)
    assert saved_goal.planner_completion_fingerprint == ""


def test_sync_ignores_tasks_not_in_flight(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    task = Task(goal_id="g1", description="not started", status="proposed")

    Monitor().sync([task], registry, memory, kpis)

    assert task.status == "proposed"


def test_sync_records_operational_kpis(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    done_task = Task(goal_id="g1", description="x", status="done")
    blocked_task = Task(goal_id="g1", description="y", status="blocked")

    # completed_total is canonical persisted lifecycle state, not a count of
    # whichever Task objects happen to be supplied to this Monitor call.
    memory.save_task(done_task)

    Monitor().sync([done_task, blocked_task], registry, memory, kpis)

    assert kpis.latest("tasks_completed") == 1.0
    assert kpis.latest("tasks_blocked") == 1.0


def test_sync_prefers_exact_failed_task_result_over_aggregate_done_report(tmp_path):
    class _Asset:
        def run(self, **kwargs):
            return {"status": "failed", "reason": "this exact task failed"}

        def report(self):
            # Deliberately contradictory aggregate report: Monitor must not
            # use this to rewrite the exact Task's real failure into done.
            return {"status": "done", "total_runs": 99}

    records = discover_manifests([FIXTURES])
    registry = Registry(
        records,
        store=JSONStore(tmp_path / "state.json"),
        instances={"sample-triggerable": _Asset()},
    )
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    task = Task(
        goal_id="g1",
        description="exact failure",
        assigned_asset_id="sample-triggerable",
        status="delegated",
    )
    memory.save_task(task)

    registry.dispatch("sample-triggerable", "run", task=task)
    Monitor().sync([task], registry, memory, kpis)

    assert task.status == "failed"
    assert memory.get_task(task.id).status == "failed"


def test_sync_prefers_exact_done_task_result_over_aggregate_failed_report(tmp_path):
    class _Asset:
        def run(self, **kwargs):
            return {"status": "done", "work": "completed"}

        def report(self):
            # Again deliberately contradictory: aggregate asset health/state
            # must not overwrite the known result of this exact Task.
            return {"status": "failed"}

    records = discover_manifests([FIXTURES])
    registry = Registry(
        records,
        store=JSONStore(tmp_path / "state.json"),
        instances={"sample-triggerable": _Asset()},
    )
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    task = Task(
        goal_id="g1",
        description="exact success",
        assigned_asset_id="sample-triggerable",
        status="delegated",
    )
    memory.save_task(task)

    registry.dispatch("sample-triggerable", "run", task=task)
    Monitor().sync([task], registry, memory, kpis)

    assert task.status == "done"
    assert memory.get_task(task.id).status == "done"
