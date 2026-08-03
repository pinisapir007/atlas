from atlas.brain.content_factory_advance import advance_content_factory
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


def _opportunity(stage, goal_id="goal-a", opp_id="opp-1", content_package=None, **overrides):
    base = {
        "id": opp_id,
        "stage": stage,
        "goal_id": goal_id,
        "product_name": "QuietDesk",
        "content_package": content_package or {},
    }
    base.update(overrides)
    return base


def _report(*opportunities):
    return {"status": "done", "opportunities": list(opportunities)}


def _memory_with_goal(tmp_path, goal_id="goal-a"):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="market the chosen opportunity", id=goal_id))
    return memory


def test_triggers_generation_for_selected_with_no_package(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("selected_for_marketing")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_content_factory([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].category == "content_factory"
    assert tasks[0].reversible is True
    assert tasks[0].source_opportunity_id is None


def test_no_generation_trigger_once_package_exists(tmp_path):
    registry = _StubRegistry(
        report=_report(_opportunity("selected_for_marketing", content_package={"variant": 0}))
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_content_factory([], registry, memory, kpis)

    assert not any(t.source_opportunity_id is None for t in tasks) or tasks == []


def test_requests_review_once_editorial_passed(tmp_path):
    registry = _StubRegistry(
        report=_report(_opportunity("editorial_passed", content_package={"variant": 0}))
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_content_factory([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].reversible is False
    assert tasks[0].source_opportunity_id == "opp-1"
    assert kpis.latest("content_packages_generated_goal-a") == 1.0


def test_no_second_review_while_first_is_still_open(tmp_path):
    registry = _StubRegistry(
        report=_report(_opportunity("editorial_passed", content_package={"variant": 0}))
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    open_review = Task(
        goal_id="goal-a",
        description="pending review",
        category="content_factory",
        status="pending_approval",
        reversible=False,
        source_opportunity_id="opp-1",
    )

    tasks = advance_content_factory([open_review], registry, memory, kpis)

    assert tasks == []


def test_rejected_review_creates_regenerate_trigger(tmp_path):
    registry = _StubRegistry(
        report=_report(_opportunity("editorial_passed", content_package={"variant": 0}))
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    rejected_review = Task(
        goal_id="goal-a",
        description="rejected review",
        category="content_factory",
        status="failed",
        reversible=False,
        source_opportunity_id="opp-1",
    )

    tasks = advance_content_factory([rejected_review], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].reversible is True
    assert tasks[0].source_opportunity_id == "opp-1"


def test_second_review_requested_after_regeneration(tmp_path):
    registry = _StubRegistry(
        report=_report(_opportunity("editorial_passed", content_package={"variant": 1}))
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    rejected_review = Task(
        goal_id="goal-a",
        description="rejected review",
        category="content_factory",
        status="failed",
        reversible=False,
        source_opportunity_id="opp-1",
    )
    regenerate_trigger = Task(
        goal_id="goal-a",
        description="regenerate",
        category="content_factory",
        status="done",
        reversible=True,
        source_opportunity_id="opp-1",
    )

    tasks = advance_content_factory([rejected_review, regenerate_trigger], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].reversible is False  # a fresh review request, not another regenerate-trigger


def test_no_task_for_approved_or_lost_opportunity(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    for stage in ("approved_for_marketing", "lost"):
        registry = _StubRegistry(report=_report(_opportunity(stage, content_package={"variant": 0})))
        assert advance_content_factory([], registry, memory, kpis) == []


def test_no_task_for_untracked_goal(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_packaged", goal_id="goal-elsewhere")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_content_factory([], registry, memory, kpis) == []


def test_returns_empty_when_asset_not_registered(tmp_path):
    registry = _StubRegistry(raise_exc=KeyError("no such asset"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_content_factory([], registry, memory, kpis) == []


def test_returns_empty_when_report_verb_unsupported(tmp_path):
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_content_factory([], registry, memory, kpis) == []


def test_campaign_claimed_goal_is_skipped_entirely(tmp_path):
    # A goal already claimed by the newer Campaign/Execution Orchestrator
    # pipeline (see campaign_advance.py) must never also get a content_factory
    # generation task — the two pipelines would otherwise race on the exact
    # same selected_for_marketing signal and double-generate content.
    registry = _StubRegistry(report=_report(_opportunity("selected_for_marketing")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_content_factory([], registry, memory, kpis, campaign_claimed_goal_ids={"goal-a"})

    assert tasks == []


def test_omitting_campaign_claimed_goal_ids_preserves_prior_behavior_exactly(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("selected_for_marketing")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_content_factory([], registry, memory, kpis)  # no campaign_claimed_goal_ids at all

    assert len(tasks) == 1


def test_an_unclaimed_goal_alongside_a_claimed_one_is_unaffected(tmp_path):
    registry = _StubRegistry(
        report=_report(
            _opportunity("selected_for_marketing", goal_id="goal-a", opp_id="opp-1"),
            _opportunity("selected_for_marketing", goal_id="goal-b", opp_id="opp-2"),
        )
    )
    memory = _memory_with_goal(tmp_path, goal_id="goal-a")
    memory.save_goal(Goal(description="a different, unclaimed goal", id="goal-b"))
    kpis = KPIRegistry(memory)

    tasks = advance_content_factory([], registry, memory, kpis, campaign_claimed_goal_ids={"goal-a"})

    assert len(tasks) == 1
    assert tasks[0].goal_id == "goal-b"
