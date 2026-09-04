from types import SimpleNamespace

import atlas.brain.video_research_advance as bridge
from atlas.brain.discovery.video_research_request import (
    parse_video_research_task,
    video_research_task_description,
)
from atlas.brain.models import Task


class FakeMemory:
    def __init__(self, tasks=None):
        self._tasks = list(tasks or [])
        self.logs = []

    def tasks(self):
        return list(self._tasks)

    def save_task(self, task):
        for index, existing in enumerate(self._tasks):
            if existing.id == task.id:
                self._tasks[index] = task
                return
        self._tasks.append(task)

    def append_log(self, entry):
        self.logs.append(entry)


class FakeKnowledge:
    def __init__(self, findings=None):
        self._findings = list(findings or [])

    def findings(self):
        return list(self._findings)


class FakeKPIs:
    def __init__(self):
        self.values = {}

    def latest(self, name):
        return self.values.get(name)

    def record(self, name, value):
        self.values[name] = value


class FakeYouTube:
    def __init__(self, ids):
        self.ids = list(ids)
        self.calls = []

    def search(self, query, max_results=5):
        self.calls.append((query, max_results))
        return [
            {"id": {"videoId": video_id}, "snippet": {"title": video_id}}
            for video_id in self.ids
        ]


def _enable(monkeypatch):
    monkeypatch.setenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", "1")
    monkeypatch.setenv("ATLAS_VIDEO_RESEARCH_ENABLED", "1")


def _patch_category_and_goal(monkeypatch, category="saas"):
    monkeypatch.setattr(
        bridge,
        "categories_needing_research",
        lambda knowledge, kpis: [category],
    )
    monkeypatch.setattr(
        bridge,
        "discovery_goal",
        lambda memory: SimpleNamespace(id="goal-discovery"),
    )


def test_bridge_is_completely_inert_when_video_flag_is_off(monkeypatch):
    monkeypatch.setenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", "1")
    monkeypatch.delenv("ATLAS_VIDEO_RESEARCH_ENABLED", raising=False)
    _patch_category_and_goal(monkeypatch)

    provider = FakeYouTube(["abc123"])

    created = bridge.advance_video_research(
        FakeMemory(),
        FakeKnowledge(),
        FakeKPIs(),
        youtube_provider=provider,
    )

    assert created == []
    assert provider.calls == []


def test_enabled_bridge_searches_once_and_creates_one_real_task(monkeypatch):
    _enable(monkeypatch)
    _patch_category_and_goal(monkeypatch)

    memory = FakeMemory()
    kpis = FakeKPIs()
    provider = FakeYouTube(["abc123", "def456"])

    created = bridge.advance_video_research(
        memory,
        FakeKnowledge(),
        kpis,
        youtube_provider=provider,
    )

    assert len(provider.calls) == 1
    assert len(created) == 1
    assert len(memory.tasks()) == 1

    task = created[0]
    category, url = parse_video_research_task(task)

    assert task.category == "video_research"
    assert task.goal_id == "goal-discovery"
    assert category == "saas"
    assert url == "https://www.youtube.com/watch?v=abc123"
    assert bridge.video_research_attempts("saas", kpis) == 1


def test_attempt_cap_prevents_repeated_search(monkeypatch):
    _enable(monkeypatch)
    _patch_category_and_goal(monkeypatch)

    memory = FakeMemory()
    knowledge = FakeKnowledge()
    kpis = FakeKPIs()
    provider = FakeYouTube(["abc123"])

    first = bridge.advance_video_research(
        memory,
        knowledge,
        kpis,
        youtube_provider=provider,
    )
    second = bridge.advance_video_research(
        memory,
        knowledge,
        kpis,
        youtube_provider=provider,
    )

    assert len(first) == 1
    assert second == []
    assert len(provider.calls) == 1


def test_bridge_skips_a_previously_known_video_url(monkeypatch):
    _enable(monkeypatch)
    _patch_category_and_goal(monkeypatch, category="saas")

    old_task = Task(
        goal_id="old-goal",
        category="video_research",
        description=video_research_task_description(
            "affiliate",
            "https://www.youtube.com/watch?v=abc123",
        ),
        reversible=True,
        status="done",
    )

    memory = FakeMemory([old_task])
    provider = FakeYouTube(["abc123", "def456"])

    created = bridge.advance_video_research(
        memory,
        FakeKnowledge(),
        FakeKPIs(),
        youtube_provider=provider,
    )

    assert len(created) == 1
    category, url = parse_video_research_task(created[0])
    assert category == "saas"
    assert url == "https://www.youtube.com/watch?v=def456"
    assert len(provider.calls) == 1
