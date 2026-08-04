from datetime import datetime, timezone

from atlas.brain.decision_engine_integration import (
    EXECUTE,
    WAIT,
    TaskExecutionRequirements,
    check_opportunity_available,
    check_resources_available,
    check_time_remaining,
    evaluate_task_readiness,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, Task
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.time_service import TimeService
from atlas.integrations.base import Resource


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _allowlist():
    return ResourceAllowlist(store=_FakeStore())


def _index():
    return ResourceIndex(store=_FakeStore())


def _knowledge():
    return KnowledgeBase(store=_FakeStore())


def _fixed_clock(moment: datetime):
    return TimeService(clock=lambda: moment)


_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# --- check_resources_available ---


def test_resources_check_passes_trivially_with_no_required_paths():
    passed, reason = check_resources_available([], _index(), _allowlist())
    assert passed is True
    assert reason is None


def test_resources_check_fails_when_path_is_not_approved():
    passed, reason = check_resources_available(["/not/approved.txt"], _index(), _allowlist())
    assert passed is False
    assert "not approved" in reason


def test_resources_check_fails_when_path_is_approved_but_not_indexed():
    allowlist = _allowlist()
    allowlist.approve_folder("/approved")
    passed, reason = check_resources_available(["/approved/missing.txt"], _index(), allowlist)
    assert passed is False
    assert "not found in the index" in reason


def test_resources_check_fails_when_indexed_resource_has_a_real_error():
    allowlist = _allowlist()
    allowlist.approve_folder("/approved")
    index = _index()
    index.replace_index([Resource(provider="local_folder", path="/approved/broken.txt", resource_type="file", error="permission denied")])

    passed, reason = check_resources_available(["/approved/broken.txt"], index, allowlist)

    assert passed is False
    assert "real scan error" in reason


def test_resources_check_passes_when_approved_and_indexed_without_error():
    allowlist = _allowlist()
    allowlist.approve_folder("/approved")
    index = _index()
    index.replace_index([Resource(provider="local_folder", path="/approved/real.txt", resource_type="file")])

    passed, reason = check_resources_available(["/approved/real.txt"], index, allowlist)

    assert passed is True
    assert reason is None


def test_resources_check_fails_if_any_one_of_several_required_paths_is_missing():
    allowlist = _allowlist()
    allowlist.approve_folder("/approved")
    index = _index()
    index.replace_index([Resource(provider="local_folder", path="/approved/a.txt", resource_type="file")])

    passed, reason = check_resources_available(["/approved/a.txt", "/approved/b.txt"], index, allowlist)

    assert passed is False
    assert "/approved/b.txt" in reason


# --- check_opportunity_available ---


def test_opportunity_check_passes_trivially_with_no_category():
    passed, reason = check_opportunity_available(None, _knowledge())
    assert passed is True
    assert reason is None


def test_opportunity_check_fails_with_no_real_findings_for_the_category():
    passed, reason = check_opportunity_available("affiliate", _knowledge())
    assert passed is False
    assert "no real opportunity recorded" in reason


def test_opportunity_check_passes_with_a_real_sourced_finding():
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="test", category="affiliate", description="real evidence", evidence="https://real.example.com", subject="KetoDNA"))

    passed, reason = check_opportunity_available("affiliate", knowledge)

    assert passed is True
    assert reason is None


def test_opportunity_check_fails_below_a_real_minimum_confidence():
    knowledge = _knowledge()
    # One sourced finding -> a real but low confidence score.
    knowledge.save_finding(Finding(source="test", category="affiliate", description="real evidence", evidence="https://real.example.com", subject="KetoDNA"))

    passed, reason = check_opportunity_available("affiliate", knowledge, min_confidence=0.99)

    assert passed is False
    assert "below the required minimum" in reason


def test_opportunity_check_never_fabricates_a_category_that_was_never_recorded():
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="test", category="digital_product", description="unrelated", subject="Other"))

    passed, reason = check_opportunity_available("affiliate", knowledge)

    assert passed is False
    assert "affiliate" in reason


# --- check_time_remaining ---


def test_time_check_passes_trivially_with_no_deadline():
    passed, reason = check_time_remaining(None, 100.0, _fixed_clock(_NOW))
    assert passed is True
    assert reason is None


def test_time_check_passes_with_enough_real_remaining_time():
    deadline = "2026-01-15T13:00:00+00:00"  # 1 real hour from _NOW
    passed, reason = check_time_remaining(deadline, 1800, _fixed_clock(_NOW))
    assert passed is True


def test_time_check_fails_with_insufficient_real_remaining_time():
    deadline = "2026-01-15T12:05:00+00:00"  # 5 real minutes from _NOW
    passed, reason = check_time_remaining(deadline, 3600, _fixed_clock(_NOW))
    assert passed is False
    assert "300.0s remain" in reason


def test_time_check_fails_when_deadline_has_already_passed():
    deadline = "2026-01-15T11:00:00+00:00"  # 1 real hour in the past
    passed, reason = check_time_remaining(deadline, 0, _fixed_clock(_NOW))
    assert passed is False
    assert "-3600.0s remain" in reason


# --- evaluate_task_readiness (the combinator) ---


def test_execute_when_every_check_passes():
    task = Task(goal_id="g1", description="do something")
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="test", category="affiliate", description="real", evidence="https://real.example.com", subject="KetoDNA"))
    requirements = TaskExecutionRequirements(opportunity_category="affiliate", deadline_iso="2026-01-15T13:00:00+00:00", minimum_remaining_seconds=60)

    readiness = evaluate_task_readiness(task, requirements, resource_index=_index(), resource_allowlist=_allowlist(), knowledge=knowledge, time_service=_fixed_clock(_NOW))

    assert readiness.decision == EXECUTE
    assert readiness.reasons == []
    assert readiness.task_id == task.id
    assert all(check["passed"] for check in readiness.checks.values())


def test_wait_with_no_requirements_at_all_still_executes():
    # Every axis gracefully passes when nothing is required -- an
    # "empty" requirements object is not itself a blocker.
    task = Task(goal_id="g1", description="do something")
    readiness = evaluate_task_readiness(task, TaskExecutionRequirements(), resource_index=_index(), resource_allowlist=_allowlist(), knowledge=_knowledge())
    assert readiness.decision == EXECUTE


def test_wait_when_only_the_resource_check_fails():
    task = Task(goal_id="g1", description="do something")
    requirements = TaskExecutionRequirements(required_resource_paths=["/not/approved.txt"])

    readiness = evaluate_task_readiness(task, requirements, resource_index=_index(), resource_allowlist=_allowlist(), knowledge=_knowledge())

    assert readiness.decision == WAIT
    assert len(readiness.reasons) == 1
    assert "not approved" in readiness.reasons[0]
    assert readiness.checks["opportunity"]["passed"] is True  # not required, correctly passed
    assert readiness.checks["time"]["passed"] is True


def test_wait_collects_every_failing_reason_not_just_the_first():
    task = Task(goal_id="g1", description="do something")
    requirements = TaskExecutionRequirements(
        required_resource_paths=["/not/approved.txt"],
        opportunity_category="affiliate",  # no findings recorded -> fails
        deadline_iso="2026-01-15T11:00:00+00:00",  # already past -> fails
        minimum_remaining_seconds=0,
    )

    readiness = evaluate_task_readiness(task, requirements, resource_index=_index(), resource_allowlist=_allowlist(), knowledge=_knowledge(), time_service=_fixed_clock(_NOW))

    assert readiness.decision == WAIT
    assert len(readiness.reasons) == 3  # all three, not just one
    assert not readiness.checks["resources"]["passed"]
    assert not readiness.checks["opportunity"]["passed"]
    assert not readiness.checks["time"]["passed"]


def test_evaluation_is_deterministic_given_the_same_real_inputs():
    task = Task(goal_id="g1", description="do something")
    requirements = TaskExecutionRequirements(opportunity_category="affiliate")
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="test", category="affiliate", description="real", evidence="https://real.example.com", subject="KetoDNA"))

    first = evaluate_task_readiness(task, requirements, resource_index=_index(), resource_allowlist=_allowlist(), knowledge=knowledge, time_service=_fixed_clock(_NOW))
    second = evaluate_task_readiness(task, requirements, resource_index=_index(), resource_allowlist=_allowlist(), knowledge=knowledge, time_service=_fixed_clock(_NOW))

    assert first.decision == second.decision == EXECUTE


def test_evaluate_task_readiness_works_with_real_default_dependencies_when_none_supplied():
    # No stores injected -- must fall back to real instances (pointed at
    # real, currently-empty .atlas/ registries in a fresh checkout) and
    # never raise.
    task = Task(goal_id="g1", description="do something")
    readiness = evaluate_task_readiness(task, TaskExecutionRequirements())
    assert readiness.decision in (EXECUTE, WAIT)
