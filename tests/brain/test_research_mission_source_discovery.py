from dataclasses import dataclass

from atlas.brain.research_mission_source_discovery import (
    advance_research_mission_source_discovery,
)
from atlas.brain.research_missions import (
    ResearchMission,
    ResearchMissionStore,
)


class _AlwaysPublic:
    def is_approved(self, url):
        return True


class _NeverPublic:
    def is_approved(self, url):
        return False


@dataclass
class _Brave:
    results: object
    error: Exception | None = None

    def __post_init__(self):
        self.calls = []

    def search(self, query, max_results=5):
        self.calls.append((query, max_results))

        if self.error is not None:
            raise self.error

        return self.results


@dataclass
class _YouTube:
    results: object

    def __post_init__(self):
        self.calls = []

    def search(self, query, max_results=5):
        self.calls.append((query, max_results))
        return self.results


def _setup(tmp_path, *, categories=None, max_sources=24, max_discovery_attempts=2):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Learn the digital business landscape",
        categories=categories or ["ugc"],
        max_sources=max_sources,
        max_discovery_attempts_per_provider=max_discovery_attempts,
    )
    store.save_mission(mission)

    return store, mission


def test_flag_off_is_exact_noop(tmp_path, monkeypatch):
    monkeypatch.delenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        raising=False,
    )

    store, mission = _setup(tmp_path)

    brave = _Brave(
        [{"url": "https://example.com/report"}]
    )
    youtube = _YouTube([])

    changed = advance_research_mission_source_discovery(
        store,
        brave_provider=brave,
        youtube_provider=youtube,
        public_https_policy=_AlwaysPublic(),
    )

    assert changed == []
    assert brave.calls == []
    assert youtube.calls == []
    assert store.discoveries(mission.id) == []
    assert store.sources(mission.id) == []
    assert store.get_mission(
        mission.id
    ).source_discovery_complete is False


def test_brave_discovers_one_normalized_public_https_source(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(tmp_path)

    brave = _Brave(
        [
            {
                "url": (
                    "https://Example.com/report/"
                    "?utm_source=test&b=2&a=1#section"
                )
            },
            {"url": "https://second.example/report"},
        ]
    )

    changed = advance_research_mission_source_discovery(
        store,
        brave_provider=brave,
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    assert len(changed) == 1

    discovery = changed[0]

    assert discovery.provider == "brave"
    assert discovery.category == "ugc"
    assert discovery.status == "completed"
    assert discovery.attempts == 1
    assert len(discovery.source_ids) == 1

    sources = store.sources(mission.id)

    assert len(sources) == 1
    assert sources[0].source_ref == (
        "https://example.com/report?a=1&b=2"
    )
    assert sources[0].source_kind == "browser"
    assert sources[0].status == "pending"


def test_brave_does_not_enqueue_nonpublic_candidate(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(tmp_path)

    changed = advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave(
            [{"url": "https://private.example/report"}]
        ),
        youtube_provider=_YouTube([]),
        public_https_policy=_NeverPublic(),
    )

    assert len(changed) == 1
    assert changed[0].status == "completed"
    assert changed[0].source_ids == []
    assert store.sources(mission.id) == []


def test_brave_skips_youtube_result_for_separate_youtube_provider(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(tmp_path)

    changed = advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave(
            [
                {
                    "url": (
                        "https://www.youtube.com/"
                        "watch?v=already-video"
                    )
                }
            ]
        ),
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    assert len(changed) == 1
    assert changed[0].provider == "brave"
    assert changed[0].source_ids == []
    assert store.sources(mission.id) == []


def test_next_call_advances_youtube_and_enqueues_canonical_url(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(tmp_path)

    # First call completes Brave.
    advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave([]),
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    youtube = _YouTube(
        [
            {
                "id": {
                    "videoId": "abc123XYZ"
                }
            }
        ]
    )

    changed = advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave([]),
        youtube_provider=youtube,
        public_https_policy=_AlwaysPublic(),
    )

    assert len(changed) == 1
    assert changed[0].provider == "youtube"
    assert changed[0].status == "completed"
    assert changed[0].attempts == 1

    sources = store.sources(mission.id)

    assert len(sources) == 1
    assert sources[0].source_ref == (
        "https://www.youtube.com/watch?v=abc123XYZ"
    )
    assert sources[0].source_kind == "youtube"


def test_provider_failure_retries_then_exhausts(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(
        tmp_path,
        max_discovery_attempts=2,
    )

    first = advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave(
            [],
            error=RuntimeError("temporary search failure"),
        ),
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    assert len(first) == 1
    assert first[0].status == "pending"
    assert first[0].attempts == 1

    second = advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave(
            [],
            error=RuntimeError("still failing"),
        ),
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    assert len(second) == 1
    assert second[0].status == "failed_exhausted"
    assert second[0].attempts == 2
    assert "still failing" in second[0].last_error


def test_one_external_search_maximum_per_invocation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, _mission = _setup(
        tmp_path,
        categories=["ugc", "saas"],
    )

    brave = _Brave([])
    youtube = _YouTube([])

    advance_research_mission_source_discovery(
        store,
        brave_provider=brave,
        youtube_provider=youtube,
        public_https_policy=_AlwaysPublic(),
    )

    assert len(brave.calls) + len(youtube.calls) == 1


def test_empty_categories_complete_discovery_without_network(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Nothing queued",
        categories=[],
    )
    store.save_mission(mission)

    brave = _Brave([])
    youtube = _YouTube([])

    changed = advance_research_mission_source_discovery(
        store,
        brave_provider=brave,
        youtube_provider=youtube,
        public_https_policy=_AlwaysPublic(),
    )

    assert changed == []
    assert brave.calls == []
    assert youtube.calls == []
    assert store.get_mission(
        mission.id
    ).source_discovery_complete is True


def test_all_required_units_terminal_marks_discovery_complete(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(tmp_path)

    advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave([]),
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    assert store.get_mission(
        mission.id
    ).source_discovery_complete is False

    advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave([]),
        youtube_provider=_YouTube([]),
        public_https_policy=_AlwaysPublic(),
    )

    restored = store.get_mission(mission.id)

    assert restored.source_discovery_complete is True

    progress = store.discoveries(mission.id)

    assert {
        (item.provider, item.status)
        for item in progress
    } == {
        ("brave", "completed"),
        ("youtube", "completed"),
    }


def test_source_budget_stops_future_discovery_cleanly(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, mission = _setup(
        tmp_path,
        max_sources=1,
    )

    advance_research_mission_source_discovery(
        store,
        brave_provider=_Brave(
            [{"url": "https://example.com/report"}]
        ),
        youtube_provider=_YouTube(
            [
                {
                    "id": {
                        "videoId": "unused"
                    }
                }
            ]
        ),
        public_https_policy=_AlwaysPublic(),
    )

    restored = store.get_mission(mission.id)

    assert len(store.sources(mission.id)) == 1
    assert restored.source_discovery_complete is True


def test_ceo_tick_source_discovery_order_is_before_ingestion_and_closure():
    import inspect

    from atlas.brain.ceo import CEOBrain

    source = inspect.getsource(CEOBrain._tick_impl)

    discovery = source.index(
        "advance_research_mission_source_discovery("
    )
    generic = source.index(
        "advance_research_mission_sources("
    )
    youtube = source.index(
        "advance_research_mission_youtube("
    )
    lifecycle = source.index(
        "advance_research_missions("
    )

    assert discovery < generic < youtube < lifecycle
