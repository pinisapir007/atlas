from atlas.brain.research_mission_advance import (
    advance_research_missions,
)
from atlas.brain.research_missions import (
    ResearchMission,
    ResearchMissionStore,
)


def make_store(tmp_path):
    store = ResearchMissionStore(tmp_path / "research_missions.json")

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad research",
    )
    store.save_mission(mission)

    return store, mission


def finish_discovery(store, mission):
    mission = store.get_mission(mission.id)
    mission.source_discovery_complete = True
    store.save_mission(mission)


def test_flag_off_is_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_RESEARCH_MISSION_ENABLED", raising=False)

    store, mission = make_store(tmp_path)

    finish_discovery(store, mission)

    assert advance_research_missions(store) == []
    assert store.get_mission(mission.id).status == "active"


def test_finished_queue_does_not_close_before_discovery_complete(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ATLAS_RESEARCH_MISSION_ENABLED", "1")

    store, mission = make_store(tmp_path)

    source = store.add_source(
        mission.id,
        "https://example.com/a",
        "ugc",
        "Check A",
    )

    source.status = "processed"
    source.finding_ids = ["finding-1"]
    store.save_source(source)

    assert advance_research_missions(store) == []
    assert store.get_mission(mission.id).status == "active"


def test_zero_sources_after_discovery_exhausts(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_RESEARCH_MISSION_ENABLED", "1")

    store, mission = make_store(tmp_path)
    finish_discovery(store, mission)

    advance_research_missions(store)

    assert store.get_mission(mission.id).status == "exhausted"


def test_processed_source_after_discovery_completes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ATLAS_RESEARCH_MISSION_ENABLED", "1")

    store, mission = make_store(tmp_path)

    source = store.add_source(
        mission.id,
        "https://example.com/a",
        "ugc",
        "Check A",
    )

    source.status = "processed"
    source.finding_ids = ["finding-1"]
    store.save_source(source)

    finish_discovery(store, mission)

    advance_research_missions(store)

    restored = store.get_mission(mission.id)

    assert restored.status == "completed"
    assert restored.completed_at is not None


def test_only_failed_or_rejected_sources_exhaust(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ATLAS_RESEARCH_MISSION_ENABLED", "1")

    store, mission = make_store(tmp_path)

    a = store.add_source(
        mission.id,
        "https://example.com/a",
        "ugc",
        "Check A",
    )
    b = store.add_source(
        mission.id,
        "https://example.com/b",
        "ugc",
        "Check B",
    )

    a.status = "rejected"
    store.save_source(a)

    b.status = "failed_exhausted"
    store.save_source(b)

    finish_discovery(store, mission)

    advance_research_missions(store)

    assert store.get_mission(mission.id).status == "exhausted"


def test_pending_source_prevents_close(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_RESEARCH_MISSION_ENABLED", "1")

    store, mission = make_store(tmp_path)

    store.add_source(
        mission.id,
        "https://example.com/a",
        "ugc",
        "Check A",
    )

    finish_discovery(store, mission)

    assert advance_research_missions(store) == []
    assert store.get_mission(mission.id).status == "active"
