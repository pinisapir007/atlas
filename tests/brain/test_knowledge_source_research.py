import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_research import EvidenceQualityRejected, collect_evidence_from_source
from atlas.integrations.base import PageObservation


class _FakePlugin:
    name = "fake"

    def __init__(self, observation):
        self._observation = observation
        self.calls = []

    def can_handle(self, source_ref):
        return True

    def observe(self, source_ref, extract=None):
        self.calls.append((source_ref, extract))
        return self._observation


class _FakeAIProvider:
    name = "fake"

    def __init__(self, relevant: bool):
        self._relevant = relevant

    def complete_structured(self, prompt, fields):
        return {"relevant": "yes" if self._relevant else "no", "reason": "fake judgment"}


def _long_text(marker="real evidence") -> str:
    return f"{marker} " * 20


def test_a_real_high_quality_observation_produces_a_real_finding(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("real keto demand")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    finding = collect_evidence_from_source(
        "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
        knowledge=knowledge, subject="keto", market="US", ai_provider=_FakeAIProvider(relevant=True),
    )

    assert finding.evidence == "some-source"
    assert finding.category == "affiliate"
    assert finding.subject == "keto"
    assert knowledge.findings() == [finding]


def test_a_real_low_quality_observation_is_rejected_not_silently_saved(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content="too short"))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    with pytest.raises(EvidenceQualityRejected):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, ai_provider=_FakeAIProvider(relevant=True),
        )

    assert knowledge.findings() == []


def test_a_real_off_task_observation_is_rejected_not_silently_saved(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("unrelated recipe content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    with pytest.raises(EvidenceQualityRejected, match="failed evidence quality"):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, ai_provider=_FakeAIProvider(relevant=False),
        )

    assert knowledge.findings() == []


def test_a_real_plugin_failure_propagates_and_is_never_recorded(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    class _FailingPlugin:
        name = "failing"

        def can_handle(self, source_ref):
            return True

        def observe(self, source_ref, extract=None):
            raise RuntimeError("real plugin failure")

    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: _FailingPlugin())

    with pytest.raises(RuntimeError, match="real plugin failure"):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="a real task",
            knowledge=knowledge,
        )

    assert knowledge.findings() == []
