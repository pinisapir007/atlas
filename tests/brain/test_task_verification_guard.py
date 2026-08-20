import pytest

from atlas.brain.models import Task, TaskVerificationRequired


def _task(**overrides) -> Task:
    defaults = dict(goal_id="g1", description="do something")
    defaults.update(overrides)
    return Task(**defaults)


# --- K: expected_outcome + verification unknown -> cannot become done ---


def test_k_task_with_expected_outcome_and_unknown_verification_cannot_become_done():
    task = _task(expected_outcome="commission rate confirmed independently")
    assert task.verification_status == "unknown"

    with pytest.raises(TaskVerificationRequired):
        task.transition("done", "actuator reported success")

    assert task.status != "done"


# --- L: verified_failure -> cannot become done ---


def test_l_task_with_verified_failure_cannot_become_done():
    task = _task(expected_outcome="commission rate confirmed independently", verification_status="verified_failure")

    with pytest.raises(TaskVerificationRequired):
        task.transition("done", "actuator reported success")


# --- M: verified_success -> may transition to done ---


def test_m_task_with_verified_success_may_transition_to_done():
    task = _task(expected_outcome="commission rate confirmed independently", verification_status="verified_success")

    task.transition("done", "independently verified")

    assert task.status == "done"


# --- N: legacy Task without expected_outcome -> unchanged behavior ---


def test_n_legacy_task_without_expected_outcome_transitions_to_done_unchanged():
    task = _task()  # expected_outcome="" (the default -- every existing Task/caller)
    assert task.expected_outcome == ""

    task.transition("done", "asset reported: ok")  # no exception, exactly today's behavior

    assert task.status == "done"


# --- try_complete(): the safe, shared fallback path ---


def test_try_complete_falls_back_to_blocked_when_verification_is_unknown():
    task = _task(expected_outcome="commission rate confirmed independently")

    completed = task.try_complete("actuator reported success")

    assert completed is False
    assert task.status == "blocked"
    assert "actuator reported success" in task.history[-1]["reason"]


def test_try_complete_succeeds_when_verified_success():
    task = _task(expected_outcome="commission rate confirmed independently", verification_status="verified_success")

    completed = task.try_complete("independently verified")

    assert completed is True
    assert task.status == "done"


def test_try_complete_on_a_legacy_task_behaves_exactly_like_before():
    task = _task()

    completed = task.try_complete("asset reported: ok")

    assert completed is True
    assert task.status == "done"


# --- C9/C10/C11 from the design audit: actuator-vs-verification disagreement ---


def test_actuator_success_but_verification_failure_never_becomes_done():
    task = _task(expected_outcome="real world change confirmed", verification_status="verified_failure")
    completed = task.try_complete("actuator: success")
    assert completed is False
    assert task.status == "blocked"


def test_actuator_failure_but_independent_verification_proves_success_can_still_complete():
    """Execution success and intent success are separate facts (locked
    ONE BRAIN principle) -- a caller that has independently verified the
    real-world outcome may still explicitly mark done, even though the
    actuator itself reported failure -- this Task model does not force
    the caller's own status choice, it only ever gates "done" on
    verification_status, exactly as designed."""
    task = _task(expected_outcome="real world change confirmed", verification_status="verified_success")
    task.transition("done", "actuator reported failure, but independent observation confirmed the real outcome")
    assert task.status == "done"


# --- P: restart preserves verification state ---


def test_p_verification_state_survives_a_real_save_and_reload_round_trip(tmp_path):
    from atlas.brain.memory import BrainMemory

    path = tmp_path / "brain.json"
    memory1 = BrainMemory(path)
    task = _task(expected_outcome="commission rate confirmed independently", verification_status="verified_success", verification_evidence_id="finding-123")
    memory1.save_task(task)
    del memory1

    memory2 = BrainMemory(path)
    reloaded = memory2.get_task(task.id)
    assert reloaded.expected_outcome == "commission rate confirmed independently"
    assert reloaded.verification_status == "verified_success"
    assert reloaded.verification_evidence_id == "finding-123"
