from atlas.brain.editorial_review_advance import advance_editorial_review
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
    base = {"id": opp_id, "stage": stage, "goal_id": goal_id, "product_name": "QuietDesk", "editorial_verdict": ""}
    base.update(overrides)
    return base


def _report(*opportunities):
    return {"status": "done", "opportunities": list(opportunities)}


def _memory_with_goal(tmp_path, goal_id="goal-a"):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="market the chosen opportunity", id=goal_id))
    return memory


def test_triggers_review_for_unreviewed_packaged_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_packaged")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_editorial_review([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].category == "editorial_review"
    assert tasks[0].reversible is True
    assert tasks[0].source_opportunity_id is None


def test_no_review_trigger_once_verdict_exists(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_packaged", editorial_verdict="revision_required")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_editorial_review([], registry, memory, kpis)

    assert not any(t.category == "editorial_review" and t.source_opportunity_id is None for t in tasks)


def test_triggers_fix_when_revision_required(tmp_path):
    registry = _StubRegistry(
        report=_report(
            _opportunity(
                "content_packaged",
                editorial_verdict="revision_required",
                editorial_cycles=1,
                editorial_feedback={"failed_sections": ["ctas"]},
            )
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_editorial_review([], registry, memory, kpis)

    fix_tasks = [t for t in tasks if t.category == "content_factory_editorial_fix"]
    assert len(fix_tasks) == 1
    assert fix_tasks[0].source_opportunity_id == "opp-1"
    assert fix_tasks[0].reversible is True
    assert "ctas" in fix_tasks[0].description


def test_no_duplicate_fix_for_the_same_cycle(tmp_path):
    registry = _StubRegistry(
        report=_report(
            _opportunity(
                "content_packaged",
                editorial_verdict="revision_required",
                editorial_cycles=1,
                editorial_feedback={"failed_sections": ["ctas"]},
            )
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    existing_fix = Task(
        goal_id="goal-a",
        description="already fixing",
        category="content_factory_editorial_fix",
        reversible=True,
        source_opportunity_id="opp-1",
    )

    tasks = advance_editorial_review([existing_fix], registry, memory, kpis)

    assert not any(t.category == "content_factory_editorial_fix" for t in tasks)


def test_new_fix_trigger_created_after_regeneration_even_if_an_old_fix_task_exists(tmp_path):
    # Reproduces the real bug: a founder-rejection regeneration resets
    # editorial_cycles to 0 and re-transitions to "content_packaged", but an
    # old fix-request task from the discarded prior generation still exists
    # in task history. It must not be counted against the new cycle.
    old_fix_task = Task(
        goal_id="goal-a",
        description="fix from a previous, now-discarded content generation",
        category="content_factory_editorial_fix",
        reversible=True,
        source_opportunity_id="opp-1",
        status="done",
    )
    old_fix_task.created_at = "2020-01-01T00:00:00+00:00"  # well before the regeneration below

    registry = _StubRegistry(
        report=_report(
            _opportunity(
                "content_packaged",
                editorial_verdict="revision_required",
                editorial_cycles=1,
                editorial_feedback={"failed_sections": ["ctas"]},
                history=[{"at": "2025-01-01T00:00:00+00:00", "stage": "content_packaged", "reason": "regenerated"}],
            )
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_editorial_review([old_fix_task], registry, memory, kpis)

    fix_tasks = [t for t in tasks if t.category == "content_factory_editorial_fix"]
    assert len(fix_tasks) == 1
    assert fix_tasks[0].source_opportunity_id == "opp-1"


def test_notifies_founder_when_editorial_rejected(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("lost", editorial_verdict="reject", editorial_cycles=2)))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_editorial_review([], registry, memory, kpis)

    assert len(tasks) == 1
    assert tasks[0].category == "editorial_review"
    assert tasks[0].reversible is False
    assert tasks[0].source_opportunity_id == "opp-1"
    assert kpis.latest("campaigns_abandoned_by_editorial_goal-a") == 1.0


def test_no_notification_for_lost_opportunity_rejected_by_founder_instead(tmp_path):
    # "lost" for a different reason (founder rejected twice, Mission 006) —
    # editorial_verdict would be "pass" by the time a founder ever saw it,
    # not "reject" — must not be mistaken for an editorial abandonment.
    registry = _StubRegistry(report=_report(_opportunity("lost", editorial_verdict="pass")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_editorial_review([], registry, memory, kpis)

    assert tasks == []


def test_never_notifies_twice_for_the_same_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("lost", editorial_verdict="reject", editorial_cycles=2)))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    already_notified = Task(
        goal_id="goal-a",
        description="already notified",
        category="editorial_review",
        reversible=False,
        source_opportunity_id="opp-1",
        status="done",
    )

    tasks = advance_editorial_review([already_notified], registry, memory, kpis)

    assert tasks == []


def test_no_task_for_untracked_goal(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("content_packaged", goal_id="goal-elsewhere")))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_editorial_review([], registry, memory, kpis) == []


def test_returns_empty_when_asset_not_registered(tmp_path):
    registry = _StubRegistry(raise_exc=KeyError("no such asset"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_editorial_review([], registry, memory, kpis) == []


def test_returns_empty_when_report_verb_unsupported(tmp_path):
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_editorial_review([], registry, memory, kpis) == []
