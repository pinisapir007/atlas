import pytest

import atlas.brain.knowledge_source_research as research
from atlas.brain.atomic_evidence import AtomicEvidence
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_research import (
    AtomicTextSourceUnsupported,
    MediaEvidenceSourceMismatch,
    collect_atomic_evidence_from_source,
)
from atlas.integrations.base import MediaEvidence, PageObservation


class _RawTextPlugin:
    name = "fake_raw_text"
    raw_text_grounded = True

    def __init__(self, observation):
        self.observation = observation
        self.calls = []

    def observe(self, source_ref, extract=None):
        self.calls.append((source_ref, extract))
        return self.observation


class _NonTextPlugin:
    name = "fake_video"

    def observe(self, source_ref, extract=None):
        raise AssertionError(
            "unsupported source must be rejected before observe()"
        )


class _AtomicProvider:
    name = "fake"

    def complete_structured(self, prompt, fields):
        if "verdict" in fields:
            return {
                "verdict": "same",
                "reason": "verified fake subject",
            }

        if "role" in fields:
            return {
                "role": "direct_assertion",
                "reason": "fake direct source",
            }

        if "atomic_1_statement" in fields:
            return {
                "atomic_1_statement": "Customers report slow delivery.",
                "atomic_1_quote": "Customers repeatedly complain about slow delivery.",
                "atomic_2_statement": "Price is listed at $29.",
                "atomic_2_quote": "The listed price is $29.",
            }

        return {
            "relevant": "yes",
            "reason": "real task-relevant fake observation",
        }


def _observation():
    return PageObservation(
        url="https://example.com/final-report",
        title="Real report",
        text_content=(
            "Research report about ExampleCo and its customers.\n"
            "Customers repeatedly complain about slow delivery.\n"
            "The listed price is $29.\n"
            "Additional real context about ExampleCo and the market. "
            "This sentence exists only to ensure the observation has "
            "enough genuine text for the normal quality gate."
        ),
        fetched_at="2026-09-03T11:00:00+00:00",
    )


def test_atomic_source_writer_persists_many_grounded_findings(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _RawTextPlugin(_observation())
    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    created = collect_atomic_evidence_from_source(
        source_ref="https://example.com/requested-report",
        category="company_research",
        source="atomic_source_test",
        task_description="identify customer pain and pricing",
        knowledge=knowledge,
        subject="ExampleCo",
        market="US",
        ai_provider=_AtomicProvider(),
        max_chunk_chars=5000,
        max_atomics_per_chunk=2,
    )

    assert len(created) == 2
    assert len(knowledge.findings()) == 2

    assert all(
        f.evidence == "https://example.com/final-report"
        for f in created
    )
    assert all(
        f.subject == "ExampleCo"
        for f in created
    )
    assert all(
        f.market == "US"
        for f in created
    )
    assert all(
        f.evidence_role == "direct_assertion"
        for f in created
    )
    assert all(
        f.observed_at == "2026-09-03T11:00:00+00:00"
        for f in created
    )
    assert all(
        len(f.content_hash) == 64
        for f in created
    )

    assert created[0].evidence_locator == "lines:2"
    assert (
        created[0].evidence_excerpt
        == "Customers repeatedly complain about slow delivery."
    )

    assert created[1].evidence_locator == "lines:3"
    assert created[1].evidence_excerpt == "The listed price is $29."


def test_repeated_atomic_source_collection_is_idempotent(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _RawTextPlugin(_observation())
    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    kwargs = dict(
        source_ref="https://example.com/report",
        category="company_research",
        source="atomic_source_test",
        task_description="identify customer pain and pricing",
        knowledge=knowledge,
        subject="ExampleCo",
        ai_provider=_AtomicProvider(),
        max_chunk_chars=5000,
        max_atomics_per_chunk=2,
    )

    first = collect_atomic_evidence_from_source(**kwargs)
    second = collect_atomic_evidence_from_source(**kwargs)

    assert len(first) == 2
    assert second == []
    assert len(knowledge.findings()) == 2


def test_non_grounded_text_plugin_is_rejected_before_observation(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: _NonTextPlugin(),
    )

    with pytest.raises(
        AtomicTextSourceUnsupported,
        match="does not guarantee real raw text",
    ):
        collect_atomic_evidence_from_source(
            source_ref="https://youtube.com/watch?v=abc",
            category="video_research",
            source="test",
            task_description="find evidence",
            knowledge=knowledge,
            ai_provider=_AtomicProvider(),
        )

    assert knowledge.findings() == []


def test_zero_verified_atomic_quotes_saves_nothing(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _RawTextPlugin(_observation())
    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    class _HallucinatingProvider(_AtomicProvider):
        def complete_structured(self, prompt, fields):
            if "atomic_1_statement" in fields:
                return {
                    "atomic_1_statement": "Invented unsupported fact.",
                    "atomic_1_quote": "This quote does not exist in the source.",
                }
            return super().complete_structured(prompt, fields)

    created = collect_atomic_evidence_from_source(
        source_ref="https://example.com/report",
        category="research",
        source="test",
        task_description="find real evidence",
        knowledge=knowledge,
        ai_provider=_HallucinatingProvider(),
        max_atomics_per_chunk=1,
    )

    assert created == []
    assert knowledge.findings() == []


class _NativeMediaPlugin:
    name = "fake_image"

    def __init__(self, items):
        self.items = items
        self.evidence_calls = []

    def observe(self, source_ref, extract=None):
        raise AssertionError(
            "native media must not be routed through PageObservation text"
        )

    def observe_evidence(self, source_ref):
        self.evidence_calls.append(source_ref)
        return self.items


def test_generic_atomic_collector_routes_native_media_without_fake_excerpt(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    media_source = "/approved/photo.png"
    plugin = _NativeMediaPlugin(
        [
            MediaEvidence(
                source_ref=media_source,
                modality="image",
                locator="image:whole",
                visual="A blue package is visible.",
                transcribed_text="PRICE: $47",
                confidence="HIGH",
                observed_at="2026-09-03T13:00:00+00:00",
                content_hash="d" * 64,
            )
        ]
    )

    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    kwargs = dict(
        source_ref=media_source,
        category="image_research",
        source="generic_media_test",
        task_description="inspect the real image",
        knowledge=knowledge,
        subject="ExampleCo",
        market="US",
        provider="fake_media",
        ai_provider=_AtomicProvider(),
    )

    first = collect_atomic_evidence_from_source(**kwargs)
    second = collect_atomic_evidence_from_source(**kwargs)

    assert len(first) == 1
    assert second == []
    assert len(knowledge.findings()) == 1
    assert plugin.evidence_calls == [media_source, media_source]

    finding = first[0]
    assert finding.evidence == media_source
    assert finding.evidence_locator == "image:whole"
    assert finding.evidence_excerpt == ""
    assert finding.observed_at == "2026-09-03T13:00:00+00:00"
    assert finding.content_hash == "d" * 64
    assert finding.provider == "fake_media"
    assert finding.subject == "ExampleCo"
    assert finding.market == "US"


def test_generic_media_collector_fails_closed_on_source_mismatch(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    plugin = _NativeMediaPlugin(
        [
            MediaEvidence(
                source_ref="/approved/a.png",
                modality="image",
                locator="image:whole",
                visual="Image A",
            ),
            MediaEvidence(
                source_ref="/approved/b.png",
                modality="image",
                locator="image:whole",
                visual="Image B",
            ),
        ]
    )

    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    with pytest.raises(MediaEvidenceSourceMismatch):
        collect_atomic_evidence_from_source(
            source_ref="/approved/a.png",
            category="image_research",
            source="test",
            task_description="inspect image",
            knowledge=knowledge,
        )

    assert knowledge.findings() == []


def test_generic_media_collector_rejects_off_task_sensor_evidence(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    plugin = _NativeMediaPlugin(
        [
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="image",
                locator="image:whole",
                visual="A blue package is visible.",
                confidence="HIGH",
            )
        ]
    )

    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    class _OffTaskProvider(_AtomicProvider):
        def complete_structured(self, prompt, fields):
            if "relevant" in fields:
                return {
                    "relevant": "no",
                    "reason": "sensor evidence does not address task",
                }
            return super().complete_structured(prompt, fields)

    with pytest.raises(
        research.EvidenceQualityRejected,
        match="failed task relevance",
    ):
        collect_atomic_evidence_from_source(
            source_ref="/approved/photo.png",
            category="image_research",
            source="test",
            task_description="find customer complaints",
            knowledge=knowledge,
            ai_provider=_OffTaskProvider(),
        )

    assert knowledge.findings() == []


def test_generic_media_collector_rejects_unverified_subject(
    tmp_path,
    monkeypatch,
):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    plugin = _NativeMediaPlugin(
        [
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="image",
                locator="image:whole",
                visual="A product package is visible.",
                confidence="HIGH",
            )
        ]
    )

    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    class _DifferentSubjectProvider(_AtomicProvider):
        def complete_structured(self, prompt, fields):
            if "verdict" in fields:
                return {
                    "verdict": "different",
                    "reason": "observed media identifies another entity",
                }
            return super().complete_structured(prompt, fields)

    with pytest.raises(
        research.SubjectAttributionUnverified,
        match="could not be confirmed",
    ):
        collect_atomic_evidence_from_source(
            source_ref="/approved/photo.png",
            category="image_research",
            source="test",
            task_description="inspect product",
            knowledge=knowledge,
            subject="ExampleCo",
            ai_provider=_DifferentSubjectProvider(),
        )

    assert knowledge.findings() == []
