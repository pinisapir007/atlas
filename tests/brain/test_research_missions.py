import pytest

from atlas.brain.research_missions import (
    ResearchMission,
    ResearchMissionStore,
)


def test_mission_round_trip(tmp_path):
    store = ResearchMissionStore(tmp_path / "research_missions.json")

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Learn digital business",
        categories=["digital_product", "ugc"],
    )

    store.save_mission(mission)

    restored = store.get_mission(mission.id)

    assert restored.goal_id == "goal-ed"
    assert restored.categories == ["digital_product", "ugc"]
    assert restored.source_discovery_complete is False
    assert restored.status == "active"


def test_source_has_category(tmp_path):
    store = ResearchMissionStore(tmp_path / "research_missions.json")

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Research UGC",
    )
    store.save_mission(mission)

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Find evidence about UGC demand",
        source_kind="browser",
    )

    assert store.get_source(source.id).category == "ugc"


def test_source_requires_category(tmp_path):
    store = ResearchMissionStore(tmp_path / "research_missions.json")

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Research",
    )
    store.save_mission(mission)

    with pytest.raises(ValueError, match="category must not be empty"):
        store.add_source(
            mission.id,
            "https://example.com/report",
            "",
            "Check report",
        )


def test_source_dedup(tmp_path):
    store = ResearchMissionStore(tmp_path / "research_missions.json")

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Research",
    )
    store.save_mission(mission)

    first = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Check report",
    )

    second = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Check report",
    )

    assert first.id == second.id
    assert len(store.sources(mission.id)) == 1


def test_source_bound(tmp_path):
    store = ResearchMissionStore(tmp_path / "research_missions.json")

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Research",
        max_sources=1,
    )
    store.save_mission(mission)

    store.add_source(
        mission.id,
        "https://example.com/a",
        "ugc",
        "Check A",
    )

    with pytest.raises(ValueError, match="max_sources=1"):
        store.add_source(
            mission.id,
            "https://example.com/b",
            "ugc",
            "Check B",
        )


def test_discovery_progress_round_trip(tmp_path):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad digital research",
        categories=["ugc"],
    )
    store.save_mission(mission)

    progress = store.ensure_discovery(
        mission.id,
        "ugc",
        "brave",
        "best ugc products to sell 2026",
    )

    restored = store.get_discovery(progress.id)

    assert restored.mission_id == mission.id
    assert restored.category == "ugc"
    assert restored.provider == "brave"
    assert restored.query == "best ugc products to sell 2026"
    assert restored.status == "pending"
    assert restored.attempts == 0
    assert restored.source_ids == []


def test_discovery_progress_is_idempotent_by_mission_category_provider(
    tmp_path,
):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad digital research",
    )
    store.save_mission(mission)

    first = store.ensure_discovery(
        mission.id,
        "ugc",
        "brave",
        "best ugc products to sell 2026",
    )

    second = store.ensure_discovery(
        mission.id,
        "ugc",
        "brave",
        "best ugc products to sell 2026",
    )

    assert first.id == second.id
    assert len(store.discoveries(mission.id)) == 1


def test_discovery_progress_rejects_query_drift(
    tmp_path,
):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad digital research",
    )
    store.save_mission(mission)

    store.ensure_discovery(
        mission.id,
        "ugc",
        "brave",
        "best ugc products to sell 2026",
    )

    with pytest.raises(
        ValueError,
        match="query mismatch",
    ):
        store.ensure_discovery(
            mission.id,
            "ugc",
            "brave",
            "a silently different query",
        )


def test_discovery_progress_requires_real_mission(
    tmp_path,
):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    with pytest.raises(
        KeyError,
        match="no such research mission",
    ):
        store.ensure_discovery(
            "missing-mission",
            "ugc",
            "brave",
            "best ugc products to sell 2026",
        )


def test_mission_discovery_attempt_bound_must_be_positive(
    tmp_path,
):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad digital research",
        max_discovery_attempts_per_provider=0,
    )

    with pytest.raises(
        ValueError,
        match="max_discovery_attempts_per_provider",
    ):
        store.save_mission(mission)
