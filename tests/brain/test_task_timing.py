from datetime import datetime, timezone

from atlas.brain.models import Task
from atlas.brain.time_service import TimeService


def _fixed_clock(moment: datetime):
    return lambda: moment


_START = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_FINISH = datetime(2026, 1, 15, 12, 5, 0, tzinfo=timezone.utc)  # 5 real minutes later


def test_new_task_has_no_timing_fields_set_yet():
    task = Task(goal_id="g1", description="do something")
    assert task.started_at is None
    assert task.finished_at is None
    assert task.duration is None
    assert task.execution_time is None


def test_transition_to_delegated_sets_started_at():
    task = Task(goal_id="g1", description="do something")
    service = TimeService(clock=_fixed_clock(_START))

    task.transition("delegated", "delegated to some_asset", time_service=service)

    assert task.started_at == _START.isoformat()


def test_transition_to_in_progress_also_sets_started_at():
    # No real code path reaches "in_progress" today, but the class's own
    # documented lifecycle names it -- honored for forward compatibility.
    task = Task(goal_id="g1", description="do something")
    service = TimeService(clock=_fixed_clock(_START))

    task.transition("in_progress", time_service=service)

    assert task.started_at == _START.isoformat()


def test_started_at_is_set_only_once_even_across_multiple_transitions():
    task = Task(goal_id="g1", description="do something")
    first_service = TimeService(clock=_fixed_clock(_START))
    task.transition("delegated", time_service=first_service)

    later_service = TimeService(clock=_fixed_clock(_FINISH))
    task.transition("prioritized", time_service=later_service)  # any later transition

    assert task.started_at == _START.isoformat()  # unchanged


def test_transition_to_done_sets_finished_at_duration_and_execution_time():
    task = Task(goal_id="g1", description="do something")
    start_service = TimeService(clock=_fixed_clock(_START))
    task.transition("delegated", time_service=start_service)

    finish_service = TimeService(clock=_fixed_clock(_FINISH))
    task.transition("done", time_service=finish_service)

    assert task.finished_at == _FINISH.isoformat()
    assert task.duration == 300.0  # real 5 minutes between started_at and finished_at
    assert task.execution_time is not None  # created_at -> finished_at, real total span


def test_transition_to_failed_also_sets_finished_at():
    task = Task(goal_id="g1", description="do something")
    task.transition("delegated", time_service=TimeService(clock=_fixed_clock(_START)))
    task.transition("failed", time_service=TimeService(clock=_fixed_clock(_FINISH)))

    assert task.finished_at == _FINISH.isoformat()
    assert task.duration == 300.0


def test_transition_to_blocked_does_not_set_finished_at():
    # A blocked task isn't necessarily over -- it can still be picked up
    # later, so it must not be stamped as finished.
    task = Task(goal_id="g1", description="do something")
    task.transition("blocked", time_service=TimeService(clock=_fixed_clock(_START)))

    assert task.finished_at is None
    assert task.duration is None


def test_finished_at_is_set_only_once_even_if_transitioned_to_done_twice():
    task = Task(goal_id="g1", description="do something")
    task.transition("delegated", time_service=TimeService(clock=_fixed_clock(_START)))
    task.transition("done", time_service=TimeService(clock=_fixed_clock(_FINISH)))

    later = datetime(2026, 1, 15, 13, 0, 0, tzinfo=timezone.utc)
    task.transition("done", time_service=TimeService(clock=_fixed_clock(later)))  # re-transition, e.g. a duplicate call

    assert task.finished_at == _FINISH.isoformat()  # unchanged, not overwritten to the later time


def test_duration_is_none_if_finished_without_ever_being_started():
    # e.g. a task that goes straight to "done" without ever passing
    # through "delegated"/"in_progress" -- no real started_at exists to
    # measure duration from, so duration honestly stays None rather
    # than being fabricated from created_at.
    task = Task(goal_id="g1", description="do something")
    task.transition("done", time_service=TimeService(clock=_fixed_clock(_FINISH)))

    assert task.started_at is None
    assert task.duration is None
    assert task.execution_time is not None  # created_at -> finished_at is still real and measurable


def test_transition_without_an_explicit_time_service_still_works_with_the_real_default():
    # No time_service passed -- must fall back to a real TimeService()
    # instance, not raise.
    task = Task(goal_id="g1", description="do something")
    task.transition("delegated")
    task.transition("done")

    assert task.started_at is not None
    assert task.finished_at is not None
    assert task.duration is not None


def test_updated_at_and_history_are_unaffected_by_the_new_timing_fields():
    # The pre-existing behavior (updated_at, history) must be byte-for-
    # byte the same as before this change.
    task = Task(goal_id="g1", description="do something")
    task.transition("delegated", "a real reason")

    assert task.status == "delegated"
    assert len(task.history) == 1
    assert task.history[0]["status"] == "delegated"
    assert task.history[0]["reason"] == "a real reason"
    assert task.updated_at == task.history[0]["at"]
