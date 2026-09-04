from atlas.assets.video_research.agent import VideoResearchAgent
from atlas.brain.delegator import Delegator
from atlas.brain.discovery.video_research_request import (
    VIDEO_RESEARCH_TASK_CATEGORY,
    parse_video_research_task,
    video_research_task_description,
)
from atlas.brain.models import Task
from atlas.core.loader import discover_manifests
from atlas.core.registry import Registry
from atlas.integrations.base import VideoEvidence


URL = "https://www.youtube.com/watch?v=test123"


class FakeKnowledge:
    def __init__(self):
        self.saved = []

    def save_finding(self, finding):
        self.saved.append(finding)

    def findings(self, category=None):
        findings = list(self.saved)
        if category is not None:
            findings = [f for f in findings if f.category == category]
        return findings


class FakeVideoProvider:
    name = "fake_video"

    def analyze_youtube(self, youtube_url, max_observations=3):
        assert youtube_url == URL
        assert max_observations == 3

        return [
            VideoEvidence(
                source_url=youtube_url,
                timestamp="02:23",
                spoken="Why, How, What.",
                visual="Three concentric circles are visible.",
                evidence_type="BOTH",
                confidence="HIGH",
            )
        ]


class FakeStore:
    def set(self, key, value):
        pass


def _task():
    return Task(
        goal_id="goal_test",
        category=VIDEO_RESEARCH_TASK_CATEGORY,
        description=video_research_task_description(
            "leadership",
            URL,
        ),
        reversible=True,
    )


def test_task_contract_round_trip():
    task = _task()

    category, url = parse_video_research_task(task)

    assert category == "leadership"
    assert url == URL


def test_agent_saves_real_timestamped_finding():
    knowledge = FakeKnowledge()
    agent = VideoResearchAgent(
        knowledge=knowledge,
        video_provider=FakeVideoProvider(),
    )

    result = agent.run(task=_task())

    assert result["status"] == "done"
    assert result["findings_created"] == 1
    assert result["provider"] == "fake_video"

    assert len(knowledge.saved) == 1
    finding = knowledge.saved[0]

    assert finding.source == "video_research"
    assert finding.category == "leadership"
    assert "Why, How, What." in finding.description
    assert "Three concentric circles" in finding.description
    assert "Evidence type: BOTH" in finding.description
    assert "Confidence: HIGH" in finding.description

    # Canonical Stage 7 evidence contract:
    # source URL remains the evidence identity; precise time is a locator.
    assert finding.evidence == URL
    assert finding.evidence_locator == "timestamp:02:23"
    assert finding.provider == "fake_video"
    assert finding.evidence_excerpt == ""
    assert finding.observed_at
    assert len(finding.content_hash) == 64


def test_delegator_routes_video_research_task_to_video_asset():
    knowledge = FakeKnowledge()
    agent = VideoResearchAgent(
        knowledge=knowledge,
        video_provider=FakeVideoProvider(),
    )

    records = discover_manifests()
    assert any(
        r.id == "video_research"
        and "video_research" in r.config.get("categories", [])
        for r in records
    )

    registry = Registry(
        records=records,
        instances={"video_research": agent},
        store=FakeStore(),
    )

    task = _task()
    result = Delegator(memory=None).delegate(task, registry)

    assert result["status"] == "done"
    assert result["findings_created"] == 1
    assert task.assigned_asset_id == "video_research"
    assert task.status == "delegated"
    assert len(knowledge.saved) == 1


def test_repeated_identical_video_observation_is_idempotent():
    knowledge = FakeKnowledge()
    agent = VideoResearchAgent(
        knowledge=knowledge,
        video_provider=FakeVideoProvider(),
    )

    first = agent.run(task=_task())
    second = agent.run(task=_task())

    assert first["status"] == "done"
    assert first["findings_created"] == 1
    assert second["status"] == "done"
    assert second["findings_created"] == 0
    assert len(knowledge.saved) == 1


class WrongSourceVideoProvider:
    name = "wrong_source_video"

    def analyze_youtube(self, youtube_url, max_observations=3):
        return [
            VideoEvidence(
                source_url="https://www.youtube.com/watch?v=DIFFERENT",
                timestamp="01:00",
                spoken="This belongs to another video.",
                evidence_type="AUDIO",
                confidence="HIGH",
            )
        ]


def test_video_agent_fails_closed_on_source_url_mismatch():
    knowledge = FakeKnowledge()
    agent = VideoResearchAgent(
        knowledge=knowledge,
        video_provider=WrongSourceVideoProvider(),
    )

    result = agent.run(task=_task())

    assert result["status"] == "failed"
    assert "source URL does not match" in result["reason"]
    assert knowledge.saved == []
