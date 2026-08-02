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

    Monitor().sync([done_task, blocked_task], registry, memory, kpis)

    assert kpis.latest("tasks_completed") == 1.0
    assert kpis.latest("tasks_blocked") == 1.0
