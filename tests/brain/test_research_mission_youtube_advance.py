from dataclasses import dataclass

from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task
from atlas.brain.research_mission_youtube_advance import (
    advance_research_mission_youtube,
)
from atlas.brain.research_missions import (
    ResearchMission,
    ResearchMissionStore,
)


YOUTUBE_URL = "https://www.youtube.com/watch?v=abc123"


@dataclass
class _Plugin:
    name: str


class _Knowledge:
    def __init__(self, findings=None):
        self._findings = list(findings or [])

    def findings(self):
        return list(self._findings)


def _setup(tmp_path, *, max_attempts=2):
    memory = BrainMemory(
        tmp_path / "brain.json"
    )

    goal = Goal(
        id="goal-ed",
        description="Executive Discovery",
    )
    memory.save_goal(goal)

    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id=goal.id,
        objective="Research broad digital evidence",
        max_attempts_per_source=max_attempts,
    )
    store.save_mission(mission)

    source = store.add_source(
        mission.id,
        YOUTUBE_URL,
        "ugc",
        "Research UGC video evidence",
        source_kind="youtube",
    )

    return memory, store, mission, source


def _enable(monkeypatch):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )
    monkeypatch.setenv(
        "ATLAS_VIDEO_RESEARCH_ENABLED",
        "1",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_youtube_advance."
        "select_plugin",
        lambda ref: _Plugin("youtube"),
    )


def test_flags_off_are_exact_noop(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        raising=False,
    )
    monkeypatch.delenv(
        "ATLAS_VIDEO_RESEARCH_ENABLED",
        raising=False,
    )

    memory, store, mission, source = _setup(tmp_path)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert changed == []
    restored = store.get_source(source.id)
    assert restored.status == "pending"
    assert restored.attempts == 0
    assert restored.task_id == ""
    assert len(memory.tasks()) == 0


def test_video_flag_off_is_noop_even_when_mission_enabled(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )
    monkeypatch.delenv(
        "ATLAS_VIDEO_RESEARCH_ENABLED",
        raising=False,
    )

    memory, store, mission, source = _setup(tmp_path)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert changed == []
    assert store.get_source(source.id).attempts == 0
    assert len(memory.tasks()) == 0


def test_existing_exact_video_findings_are_reused(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    findings = [
        Finding(
            id="finding-video-a",
            source="video_research",
            category="ugc",
            description="real timestamped evidence",
            evidence=YOUTUBE_URL + " @ 00:12",
        ),
        Finding(
            id="finding-video-b",
            source="video_research",
            category="ugc",
            description="more real evidence",
            evidence=YOUTUBE_URL + " @ 00:41",
        ),
    ]

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(findings),
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)

    assert restored.status == "processed"
    assert restored.finding_ids == [
        "finding-video-a",
        "finding-video-b",
    ]
    assert restored.attempts == 0
    assert restored.task_id == ""
    assert len(memory.tasks()) == 0


def test_new_youtube_source_creates_normal_video_task(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)
    tasks = memory.tasks()

    assert restored.status == "pending"
    assert restored.attempts == 1
    assert restored.task_id
    assert len(tasks) == 1
    assert tasks[0].id == restored.task_id
    assert tasks[0].goal_id == mission.goal_id
    assert tasks[0].category == "video_research"
    assert YOUTUBE_URL in tasks[0].description
    assert "category: ugc" in tasks[0].description


def test_inflight_correlated_task_is_not_duplicated(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    first = store.get_source(source.id)
    first_task_id = first.task_id

    second_changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    second = store.get_source(source.id)

    assert second_changed == []
    assert second.task_id == first_task_id
    assert second.attempts == 1
    assert len(memory.tasks()) == 1


def test_done_task_with_exact_findings_marks_processed(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    correlated = store.get_source(source.id)
    task = memory.get_task(correlated.task_id)
    task.status = "done"
    memory.save_task(task)

    knowledge = _Knowledge(
        [
            Finding(
                id="finding-video-real",
                source="video_research",
                category="ugc",
                description="timestamped",
                evidence=YOUTUBE_URL + " @ 01:03",
            )
        ]
    )

    changed = advance_research_mission_youtube(
        store,
        memory,
        knowledge,
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)

    assert restored.status == "processed"
    assert restored.finding_ids == [
        "finding-video-real"
    ]
    assert restored.attempts == 1


def test_done_task_without_findings_is_rejected(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    correlated = store.get_source(source.id)
    task = memory.get_task(correlated.task_id)
    task.status = "done"
    memory.save_task(task)

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    restored = store.get_source(source.id)

    assert restored.status == "rejected"
    assert restored.attempts == 1
    assert "zero exact durable Findings" in restored.last_error


def test_failed_task_releases_correlation_for_bounded_retry(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(
        tmp_path,
        max_attempts=2,
    )

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    first = store.get_source(source.id)
    first_task = memory.get_task(first.task_id)
    first_task.status = "failed"
    memory.save_task(first_task)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert len(changed) == 1

    after_failure = store.get_source(source.id)

    assert after_failure.status == "pending"
    assert after_failure.attempts == 1
    assert after_failure.task_id == ""

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    retried = store.get_source(source.id)

    assert retried.status == "pending"
    assert retried.attempts == 2
    assert retried.task_id
    assert retried.task_id != first_task.id
    assert len(memory.tasks()) == 2


def test_failed_task_exhausts_at_bound(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(
        tmp_path,
        max_attempts=1,
    )

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    correlated = store.get_source(source.id)
    task = memory.get_task(correlated.task_id)
    task.status = "failed"
    memory.save_task(task)

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    restored = store.get_source(source.id)

    assert restored.status == "failed_exhausted"
    assert restored.attempts == 1
    assert restored.task_id == task.id


def test_existing_matching_open_task_is_adopted_without_new_attempt(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    task = Task(
        goal_id=mission.goal_id,
        category="video_research",
        description=(
            f"Research YouTube video: {YOUTUBE_URL}"
            " | category: ugc"
        ),
        reversible=True,
    )
    memory.save_task(task)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)

    assert restored.task_id == task.id
    assert restored.attempts == 0
    assert len(memory.tasks()) == 1


def test_non_youtube_source_is_ignored(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory = BrainMemory(tmp_path / "brain.json")

    goal = Goal(
        id="goal-ed",
        description="Executive Discovery",
    )
    memory.save_goal(goal)

    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )
    mission = ResearchMission(
        goal_id=goal.id,
        objective="Research",
    )
    store.save_mission(mission)

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Research UGC",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_youtube_advance."
        "select_plugin",
        lambda ref: _Plugin("browser"),
    )

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert changed == []
    assert store.get_source(source.id).task_id == ""
    assert len(memory.tasks()) == 0


def test_blocked_correlated_task_remains_resumable_without_duplicate(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(
        tmp_path,
        max_attempts=2,
    )

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    correlated = store.get_source(source.id)
    task = memory.get_task(correlated.task_id)
    task.status = "blocked"
    memory.save_task(task)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    restored = store.get_source(source.id)

    assert changed == []
    assert restored.status == "pending"
    assert restored.task_id == task.id
    assert restored.attempts == 1
    assert len(memory.tasks()) == 1


def test_superseded_correlated_task_releases_for_bounded_retry(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(
        tmp_path,
        max_attempts=2,
    )

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    correlated = store.get_source(source.id)
    first_task = memory.get_task(correlated.task_id)
    first_task.status = "superseded"
    memory.save_task(first_task)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert len(changed) == 1

    after_supersession = store.get_source(source.id)

    assert after_supersession.status == "pending"
    assert after_supersession.attempts == 1
    assert after_supersession.task_id == ""

    advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    retried = store.get_source(source.id)

    assert retried.status == "pending"
    assert retried.attempts == 2
    assert retried.task_id
    assert retried.task_id != first_task.id
    assert len(memory.tasks()) == 2


def test_existing_blocked_matching_task_is_adopted_as_resumable(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    task = Task(
        goal_id=mission.goal_id,
        category="video_research",
        description=(
            f"Research YouTube video: {YOUTUBE_URL}"
            " | category: ugc"
        ),
        reversible=True,
        status="blocked",
    )
    memory.save_task(task)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)

    assert restored.status == "pending"
    assert restored.task_id == task.id
    assert restored.attempts == 0
    assert len(memory.tasks()) == 1


def test_existing_superseded_task_is_not_adopted_as_open(
    tmp_path,
    monkeypatch,
):
    _enable(monkeypatch)

    memory, store, mission, source = _setup(tmp_path)

    old_task = Task(
        goal_id=mission.goal_id,
        category="video_research",
        description=(
            f"Research YouTube video: {YOUTUBE_URL}"
            " | category: ugc"
        ),
        reversible=True,
        status="superseded",
    )
    memory.save_task(old_task)

    changed = advance_research_mission_youtube(
        store,
        memory,
        _Knowledge(),
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)

    assert restored.status == "pending"
    assert restored.attempts == 1
    assert restored.task_id
    assert restored.task_id != old_task.id
    assert len(memory.tasks()) == 2
