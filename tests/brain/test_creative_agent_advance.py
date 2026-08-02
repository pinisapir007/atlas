from atlas.brain.creative_agent_advance import advance_creative_agent
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.core.registry import UnsupportedVerb


class _StubRegistry:
    def __init__(self, report=None, raise_exc=None):
        self._report = report
        self._raise = raise_exc

    def dispatch(self, asset_id, verb):
        if self._raise is not None:
            raise self._raise
        return self._report


def _opportunity(stage, goal_id="goal-a", opp_id="opp-1", **overrides):
    base = {"id": opp_id, "stage": stage, "goal_id": goal_id, "product_name": "QuietDesk", "creative_assets": {}}
    base.update(overrides)
    return base


def _report(*opportunities):
    return {"status": "done", "opportunities": list(opportunities)}


def _memory_with_goal(tmp_path, goal_id="goal-a"):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="market the chosen opportunity", id=goal_id))
    return memory


def test_triggers_brief_for_approved_opportunity_with_no_creative_assets(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("approved_for_marketing")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_creative_agent([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].category == "creative_agent"
    assert tasks[0].reversible is True
    assert tasks[0].source_opportunity_id is None


def test_no_trigger_once_creative_assets_exist(tmp_path):
    registry = _StubRegistry(
        report=_report(_opportunity("approved_for_marketing", creative_assets={"status": "brief_ready"}))
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_creative_agent([], registry, memory, kpis)

    assert tasks == []


def test_no_trigger_for_a_different_stage(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_packaged")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_creative_agent([], registry, memory, kpis)

    assert tasks == []


def test_no_duplicate_trigger_when_one_is_already_open(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("approved_for_marketing")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    existing = Task(goal_id="goal-a", description="already drafting", category="creative_agent", reversible=True)

    tasks = advance_creative_agent([existing], registry, memory, kpis)

    assert tasks == []


def test_no_task_for_untracked_goal(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("approved_for_marketing", goal_id="goal-elsewhere")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    assert advance_creative_agent([], registry, memory, kpis) == []


def test_returns_empty_when_asset_not_registered(tmp_path):
    registry = _StubRegistry(raise_exc=KeyError("no such asset"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_creative_agent([], registry, memory, kpis) == []


def test_returns_empty_when_report_verb_unsupported(tmp_path):
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_creative_agent([], registry, memory, kpis) == []
