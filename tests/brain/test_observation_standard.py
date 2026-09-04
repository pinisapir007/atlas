from types import SimpleNamespace

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.observation_metadata import (
    observation_content_hash,
    observation_observed_at,
)
from atlas.integrations.base import PageObservation
import atlas.brain.knowledge_source_research as research


def test_legacy_finding_remains_backward_compatible():
    finding = Finding(
        source="legacy",
        category="research",
        description="old durable evidence",
    )

    assert finding.observed_at == ""
    assert finding.evidence_locator == ""
    assert finding.content_hash == ""


def test_content_hash_is_stable_and_detects_real_change():
    a = PageObservation(
        url="https://example.com/a",
        title="A",
        text_content="real content",
    )
    b = PageObservation(
        url="https://example.com/a",
        title="A",
        text_content="real content",
    )
    changed = PageObservation(
        url="https://example.com/a",
        title="A",
        text_content="real content changed",
    )

    assert observation_content_hash(a) == observation_content_hash(b)
    assert observation_content_hash(a) != observation_content_hash(changed)


def test_real_sensor_timestamp_is_preserved():
    observation = PageObservation(
        url="https://example.com",
        title="Example",
        text_content="evidence",
        fetched_at="2026-09-03T10:00:00+00:00",
    )

    assert observation_observed_at(observation) == "2026-09-03T10:00:00+00:00"


def test_general_source_writer_persists_observation_metadata(tmp_path, monkeypatch):
    observation = PageObservation(
        url="https://example.com/research",
        title="Research",
        text_content="real observed evidence about demand",
        fetched_at="2026-09-03T10:15:00+00:00",
    )

    class FakePlugin:
        name = "fake"

        def observe(self, source_ref, extract=None):
            return observation

    monkeypatch.setattr(research, "select_plugin", lambda source_ref: FakePlugin())
    monkeypatch.setattr(
        research,
        "assess_observation_quality",
        lambda *args, **kwargs: SimpleNamespace(passed=True, reason="real evidence"),
    )
    monkeypatch.setattr(
        research,
        "classify_evidence_role",
        lambda *args, **kwargs: "direct_assertion",
    )

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    finding = research.collect_evidence_from_source(
        source_ref="https://example.com/research",
        category="market_research",
        source="test_sensor",
        task_description="find real demand evidence",
        knowledge=knowledge,
    )

    assert finding.observed_at == "2026-09-03T10:15:00+00:00"
    assert finding.content_hash == observation_content_hash(observation)
    assert len(finding.content_hash) == 64

    persisted = knowledge.get_finding(finding.id)
    assert persisted.observed_at == finding.observed_at
    assert persisted.content_hash == finding.content_hash


def test_legacy_finding_has_empty_evidence_excerpt():
    finding = Finding(
        source="legacy",
        category="research",
        description="old finding",
    )

    assert finding.evidence_excerpt == ""
