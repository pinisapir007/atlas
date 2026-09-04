from atlas.brain.atomic_evidence import (
    AtomicEvidence,
    atomic_from_video_evidence,
    persist_atomic_evidence,
)
from atlas.brain.evidence_provenance import independent_source_count
from atlas.brain.knowledge import KnowledgeBase
from atlas.integrations.base import VideoEvidence


def test_one_source_can_persist_many_precise_findings(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    created = persist_atomic_evidence(
        [
            AtomicEvidence("first real fact", locator="lines:1-4"),
            AtomicEvidence("second real fact", locator="lines:5-8"),
            AtomicEvidence("third real fact", locator="lines:9-12"),
        ],
        evidence="https://example.com/report",
        source="atomic_test",
        category="market_research",
        knowledge=knowledge,
        default_evidence_role="direct_assertion",
        default_observed_at="2026-09-03T10:00:00+00:00",
        default_content_hash="source-hash-a",
    )

    assert len(created) == 3
    assert len(knowledge.findings()) == 3
    assert [f.evidence_locator for f in created] == [
        "lines:1-4",
        "lines:5-8",
        "lines:9-12",
    ]

    # Three atomic facts from one real URL are still ONE independent
    # real-world source, never three fake corroborating sources.
    assert independent_source_count(created) == 1


def test_repeated_identical_atomic_extraction_is_idempotent(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    atomic = AtomicEvidence(
        "real unchanged fact",
        locator="lines:10-12",
        content_hash="same-source-hash",
    )

    first = persist_atomic_evidence(
        [atomic],
        evidence="https://example.com/a",
        source="atomic_test",
        category="research",
        knowledge=knowledge,
    )
    second = persist_atomic_evidence(
        [atomic],
        evidence="https://example.com/a",
        source="atomic_test",
        category="research",
        knowledge=knowledge,
    )

    assert len(first) == 1
    assert second == []
    assert len(knowledge.findings()) == 1


def test_changed_source_hash_is_preserved_as_new_longitudinal_observation(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    first = persist_atomic_evidence(
        [AtomicEvidence("price is $10", locator="lines:2-2", content_hash="version-a")],
        evidence="https://example.com/product",
        source="atomic_test",
        category="pricing",
        knowledge=knowledge,
    )
    second = persist_atomic_evidence(
        [AtomicEvidence("price is $10", locator="lines:2-2", content_hash="version-b")],
        evidence="https://example.com/product",
        source="atomic_test",
        category="pricing",
        knowledge=knowledge,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert len(knowledge.findings()) == 2


def test_video_evidence_reuses_real_timestamp_as_locator():
    atomics = atomic_from_video_evidence(
        [
            VideoEvidence(
                source_url="https://youtube.com/watch?v=abc",
                timestamp="02:18",
                spoken="Retention matters after the click.",
                visual="Audience-retention graph is visible.",
                evidence_type="BOTH",
                confidence="HIGH",
            )
        ]
    )

    assert len(atomics) == 1
    assert atomics[0].locator == "timestamp:02:18"
    assert "Retention matters" in atomics[0].description
    assert "Audience-retention graph" in atomics[0].description


def test_empty_or_unlocated_video_observations_are_not_promoted():
    atomics = atomic_from_video_evidence(
        [
            VideoEvidence(
                source_url="https://youtube.com/watch?v=abc",
                timestamp="",
                spoken="something",
            ),
            VideoEvidence(
                source_url="https://youtube.com/watch?v=abc",
                timestamp="03:00",
                spoken="",
                visual="",
            ),
        ]
    )

    assert atomics == []


def test_exact_excerpt_is_persisted_and_drives_dedup(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    first = persist_atomic_evidence(
        [
            AtomicEvidence(
                description="Customers report delivery delays.",
                locator="lines:4",
                evidence_excerpt="Customers repeatedly complain about slow delivery.",
                content_hash="same-source-version",
            )
        ],
        evidence="https://example.com/report",
        source="atomic_test",
        category="customer_pain",
        knowledge=knowledge,
    )

    second = persist_atomic_evidence(
        [
            AtomicEvidence(
                # Same proven quote, slightly different paraphrase.
                description="Slow delivery is a recurring complaint.",
                locator="lines:4",
                evidence_excerpt="Customers repeatedly complain about slow delivery.",
                content_hash="same-source-version",
            )
        ],
        evidence="https://example.com/report",
        source="atomic_test",
        category="customer_pain",
        knowledge=knowledge,
    )

    assert len(first) == 1
    assert first[0].evidence_excerpt == "Customers repeatedly complain about slow delivery."
    assert second == []
    assert len(knowledge.findings()) == 1
