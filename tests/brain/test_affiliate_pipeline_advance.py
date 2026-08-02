from atlas.brain.affiliate_pipeline_advance import advance_affiliate_pipeline
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
    base = {
        "id": opp_id,
        "stage": stage,
        "goal_id": goal_id,
        "product_name": "Test Product",
        "estimated_conversion": 0.05,
        "commission_per_conversion": 25.0,
        "competition": 0.2,
        "content_difficulty": 0.2,
    }
    base.update(overrides)
    return base


def _report(*opportunities):
    return {"status": "done", "opportunities": list(opportunities)}


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def _memory_with_goal(tmp_path, goal_id="goal-a"):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="grow affiliate revenue", id=goal_id))
    return memory


def test_creates_approval_task_for_content_planned_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_planned")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_affiliate_pipeline([], registry, memory, kpis)

    assert len(tasks) == 1
    task = tasks[0]
    assert task.category == "affiliate_pipeline"
    assert task.goal_id == "goal-a"
    assert task.reversible is False
    assert task.source_opportunity_id == "opp-1"


def test_continuation_nudge_created_for_discovered_or_selected_stage(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    for stage in ("discovered", "selected"):
        registry = _StubRegistry(report=_report(_opportunity(stage)))
        tasks = advance_affiliate_pipeline([], registry, memory, kpis)
        assert len(tasks) == 1
        assert tasks[0].category == "affiliate_pipeline"
        assert tasks[0].reversible is True
        assert tasks[0].source_opportunity_id is None  # goal-level nudge, not opportunity-specific


def test_no_duplicate_nudge_when_one_is_already_open(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("discovered")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    existing_open_nudge = Task(
        goal_id="goal-a",
        description="already nudging",
        category="affiliate_pipeline",
        status="proposed",
    )

    tasks = advance_affiliate_pipeline([existing_open_nudge], registry, memory, kpis)

    assert tasks == []


def test_new_nudge_created_once_previous_nudge_is_done(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("selected")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    resolved_nudge = Task(
        goal_id="goal-a",
        description="finished last cycle",
        category="affiliate_pipeline",
        status="done",
    )

    tasks = advance_affiliate_pipeline([resolved_nudge], registry, memory, kpis)

    assert len(tasks) == 1


def test_no_task_for_lost_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("lost")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_affiliate_pipeline([], registry, memory, kpis) == []


def test_no_task_for_untagged_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_planned", goal_id=None)))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_affiliate_pipeline([], registry, memory, kpis) == []


def test_no_task_for_opportunity_whose_goal_is_not_tracked_by_this_brain(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_planned", goal_id="goal-elsewhere")))
    memory = _memory_with_goal(tmp_path)  # only tracks "goal-a"
    kpis = KPIRegistry(memory)
    assert advance_affiliate_pipeline([], registry, memory, kpis) == []


def test_never_requests_approval_twice_even_if_prior_task_is_resolved(tmp_path):
    # Unlike Recruitment's continuation mechanism, this is a one-time gate:
    # once an approval request has ever been created for this opportunity,
    # never create another one, regardless of that task's current status.
    registry = _StubRegistry(report=_report(_opportunity("content_planned")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    resolved_task = Task(
        goal_id="goal-a",
        description="already resolved",
        category="affiliate_pipeline",
        status="done",
        source_opportunity_id="opp-1",
    )

    tasks = advance_affiliate_pipeline([resolved_task], registry, memory, kpis)

    assert tasks == []


def test_records_projected_kpis_when_creating_approval_task(tmp_path):
    registry = _StubRegistry(
        report=_report(
            _opportunity(
                "content_planned",
                estimated_conversion=0.05,
                commission_per_conversion=25.0,
                competition=0.2,
                content_difficulty=0.2,
            )
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    advance_affiliate_pipeline([], registry, memory, kpis)

    assert kpis.latest("expected_ctr_goal-a") == 0.03
    assert kpis.latest("expected_conversion_goal-a") == 0.05
    assert kpis.latest("expected_revenue_goal-a") == 0.05 * 25.0 * 500
    assert kpis.latest("risk_score_goal-a") == (0.2 + 0.2) / 2
    # Never written to the real/measured KPI series
    assert kpis.latest("revenue_goal-a") is None
    assert kpis.latest("cost_goal-a") is None


def test_no_kpis_recorded_when_no_approval_task_is_created(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("discovered")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    advance_affiliate_pipeline([], registry, memory, kpis)

    assert kpis.names() == []


def test_returns_empty_when_asset_not_registered(tmp_path):
    registry = _StubRegistry(raise_exc=KeyError("no such asset: affiliate_department"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_affiliate_pipeline([], registry, memory, kpis) == []


def test_returns_empty_when_report_verb_unsupported(tmp_path):
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_affiliate_pipeline([], registry, memory, kpis) == []


def test_returns_empty_when_report_shape_unrecognized(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    registry = _StubRegistry(report={"status": "done"})  # no "opportunities" key
    assert advance_affiliate_pipeline([], registry, memory, kpis) == []

    registry_not_a_dict = _StubRegistry(report="not a dict")
    assert advance_affiliate_pipeline([], registry_not_a_dict, memory, kpis) == []
