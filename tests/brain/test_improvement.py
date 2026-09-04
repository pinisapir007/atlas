from atlas.brain.improvement import propose_improvements
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task


def test_no_evidence_no_candidates(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    assert propose_improvements(kpis, [], [], [goal]) == []


def test_stagnant_kpi_produces_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    for value in (100.0, 100.0, 100.0):
        kpis.record("revenue", value)

    candidates = propose_improvements(kpis, [], [], [goal])

    assert len(candidates) == 1
    assert candidates[0].category == "redesign_operational_architecture"
    assert candidates[0].goal_id == goal.id


def test_improving_kpi_produces_no_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    for value in (100.0, 110.0, 130.0):
        kpis.record("revenue", value)

    assert propose_improvements(kpis, [], [], [goal]) == []


def test_lower_is_better_tasks_blocked_decrease_is_improvement(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)

    for value in (10.0, 5.0, 1.0):
        kpis.record("tasks_blocked", value)

    assert propose_improvements(kpis, [], [], [goal]) == []


def test_tasks_blocked_at_zero_is_healthy_not_stagnant(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)

    for value in (0.0, 0.0, 0.0):
        kpis.record("tasks_blocked", value)

    assert propose_improvements(kpis, [], [], [goal]) == []


def test_tasks_blocked_flat_above_zero_can_produce_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)

    for value in (8.0, 8.0, 8.0):
        kpis.record("tasks_blocked", value)

    candidates = propose_improvements(kpis, [], [], [goal])

    assert len(candidates) == 1
    assert candidates[0].category == "redesign_operational_architecture"
    assert "tasks_blocked" in candidates[0].description


def test_pending_approvals_decrease_is_improvement(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)

    for value in (12.0, 7.0, 3.0):
        kpis.record("pending_approvals", value)

    assert propose_improvements(kpis, [], [], [goal]) == []


def test_ambiguous_publish_queue_snapshot_is_not_generic_stagnation_evidence(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)

    for value in (0.0, 0.0, 0.0):
        kpis.record("publish_queue_failed_goal-g1", value)

    assert propose_improvements(kpis, [], [], [goal]) == []


def test_unknown_kpi_is_not_interpreted_without_explicit_semantics(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)

    for value in (5.0, 5.0, 5.0):
        kpis.record("some_future_metric", value)

    assert propose_improvements(kpis, [], [], [goal]) == []


def test_no_active_goal_means_no_candidates(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    for value in (100.0, 100.0, 100.0):
        kpis.record("revenue", value)
    assert propose_improvements(kpis, [], [], []) == []


def test_cooldown_blocks_repeat_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    for value in (100.0, 100.0, 100.0):
        kpis.record("revenue", value)

    existing = Task(
        goal_id=goal.id,
        description="prior proposal",
        category="redesign_operational_architecture",
        status="pending_approval",
    )

    assert propose_improvements(kpis, [], [existing], [goal]) == []


def test_low_success_rate_produces_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    log = [{"category": "launch_campaign", "status": "failed"}] * 3 + [
        {"category": "launch_campaign", "status": "done"}
    ]

    candidates = propose_improvements(kpis, log, [], [goal])

    assert any(c.category == "improve_workflow" for c in candidates)


def test_healthy_success_rate_produces_no_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    log = [{"category": "launch_campaign", "status": "done"}] * 4

    assert propose_improvements(kpis, log, [], [goal]) == []


def test_workflow_improvement_candidate_is_reversible_and_not_redesign_prefixed(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    log = [{"category": "launch_campaign", "status": "failed"}] * 3 + [
        {"category": "launch_campaign", "status": "done"}
    ]

    candidates = propose_improvements(kpis, log, [], [goal])
    candidate = next(c for c in candidates if c.category == "improve_workflow")

    # Per standing policy (2026-08-02): workflow/automation/performance
    # tuning is pre-approved, not gated behind the redesign_ prefix that
    # core-architecture changes still use.
    assert candidate.reversible is True
    assert not candidate.category.startswith("redesign_")


def test_stagnant_kpi_candidate_stays_gated_as_core_architecture(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    for value in (100.0, 100.0, 100.0):
        kpis.record("revenue", value)

    candidates = propose_improvements(kpis, [], [], [goal])

    assert candidates[0].category == "redesign_operational_architecture"
    assert candidates[0].reversible is False
