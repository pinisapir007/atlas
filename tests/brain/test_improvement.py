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

    assert any(c.category == "redesign_workflow" for c in candidates)


def test_healthy_success_rate_produces_no_candidate(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    goal = Goal(description="grow", priority=1)
    log = [{"category": "launch_campaign", "status": "done"}] * 4

    assert propose_improvements(kpis, log, [], [goal]) == []
