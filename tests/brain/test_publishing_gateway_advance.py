from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.brain.publishing_gateway_advance import advance_publishing_gateway
from atlas.core.registry import UnsupportedVerb


class _StubRegistry:
    def __init__(self, report=None, raise_exc=None):
        self._report = report
        self._raise = raise_exc

    def dispatch(self, asset_id, verb):
        if self._raise is not None:
            raise self._raise
        return self._report


def _package(status, goal_id="goal-a", pkg_id="pub-1", **overrides):
    base = {"id": pkg_id, "status": status, "goal_id": goal_id, "title": "QuietDesk", "platform": "TikTok"}
    base.update(overrides)
    return base


def _report(packages=None, pending_opportunities=None):
    return {"status": "done", "packages": packages or [], "pending_opportunities": pending_opportunities or []}


def _memory_with_goal(tmp_path, goal_id="goal-a"):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="publish the approved campaign", id=goal_id))
    return memory


def test_triggers_build_for_pending_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(pending_opportunities=[{"id": "opp-1", "goal_id": "goal-a"}]))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_publishing_gateway([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].category == "publishing_gateway"
    assert tasks[0].reversible is True
    assert tasks[0].source_opportunity_id is None


def test_requests_queue_approval_for_ready_package(tmp_path):
    registry = _StubRegistry(report=_report(packages=[_package("READY")]))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_publishing_gateway([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].reversible is False
    assert tasks[0].source_opportunity_id == "pub-1"
    assert "Approve Queue" in tasks[0].description


def test_no_duplicate_approval_while_one_is_open(tmp_path):
    registry = _StubRegistry(report=_report(packages=[_package("READY")]))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    open_approval = Task(
        goal_id="goal-a",
        description="pending",
        category="publishing_gateway",
        status="pending_approval",
        reversible=False,
        source_opportunity_id="pub-1",
    )

    tasks = advance_publishing_gateway([open_approval], registry, memory, kpis)

    assert tasks == []


def test_rejected_approval_creates_cancel_trigger(tmp_path):
    registry = _StubRegistry(report=_report(packages=[_package("READY")]))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    rejected = Task(
        goal_id="goal-a",
        description="rejected",
        category="publishing_gateway",
        status="failed",
        reversible=False,
        source_opportunity_id="pub-1",
    )

    tasks = advance_publishing_gateway([rejected], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].reversible is True
    assert tasks[0].source_opportunity_id == "pub-1"


def test_no_task_for_queued_approved_failed_or_cancelled_package(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    for status in ("QUEUED", "APPROVED", "FAILED", "CANCELLED"):
        registry = _StubRegistry(report=_report(packages=[_package(status)]))
        tasks = advance_publishing_gateway([], registry, memory, kpis)
        assert tasks == []


def test_records_queue_snapshot_kpis(tmp_path):
    registry = _StubRegistry(
        report=_report(packages=[_package("READY", pkg_id="pub-1"), _package("QUEUED", pkg_id="pub-2")])
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    advance_publishing_gateway([], registry, memory, kpis)

    assert kpis.latest("publish_queue_ready_goal-a") == 1.0


def test_queue_snapshot_zeroes_out_status_once_nothing_occupies_it(tmp_path):
    # Regression: a package moving READY -> QUEUED must make "ready" read 0,
    # not silently keep showing the last nonzero count forever.
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    registry_ready = _StubRegistry(report=_report(packages=[_package("READY", pkg_id="pub-1")]))
    advance_publishing_gateway([], registry_ready, memory, kpis)
    assert kpis.latest("publish_queue_ready_goal-a") == 1.0
    assert kpis.latest("publish_queue_queued_goal-a") == 0.0

    registry_queued = _StubRegistry(report=_report(packages=[_package("QUEUED", pkg_id="pub-1")]))
    advance_publishing_gateway([], registry_queued, memory, kpis)
    assert kpis.latest("publish_queue_ready_goal-a") == 0.0
    assert kpis.latest("publish_queue_queued_goal-a") == 1.0
    assert kpis.latest("publish_queue_queued_goal-a") == 1.0


def test_no_task_for_untracked_goal(tmp_path):
    registry = _StubRegistry(report=_report(packages=[_package("READY", goal_id="goal-elsewhere")]))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_publishing_gateway([], registry, memory, kpis) == []


def test_returns_empty_when_asset_not_registered(tmp_path):
    registry = _StubRegistry(raise_exc=KeyError("no such asset"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_publishing_gateway([], registry, memory, kpis) == []


def test_returns_empty_when_report_verb_unsupported(tmp_path):
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_publishing_gateway([], registry, memory, kpis) == []
