from atlas.brain.atomic_evidence import (
    atomic_from_media_evidence,
    persist_atomic_evidence,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.integrations.base import MediaEvidence


def test_image_media_evidence_preserves_visual_observation_without_fake_excerpt():
    atomics = atomic_from_media_evidence(
        [
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="image",
                locator="image:whole",
                visual="A product package is visible on a table.",
                transcribed_text="KetoDNA",
                confidence="HIGH",
            )
        ],
        default_content_hash="a" * 64,
    )

    assert len(atomics) == 1
    atomic = atomics[0]

    assert atomic.locator == "image:whole"
    assert "Modality: IMAGE" in atomic.description
    assert "A product package is visible" in atomic.description
    assert "Transcribed: KetoDNA" in atomic.description
    assert "Confidence: HIGH" in atomic.description

    # Critical honesty rule: Gemini media interpretation is NOT treated
    # as character-for-character grounded source text.
    assert atomic.evidence_excerpt == ""
    assert atomic.content_hash == "a" * 64


def test_audio_media_evidence_preserves_audible_and_transcribed_content():
    atomics = atomic_from_media_evidence(
        [
            MediaEvidence(
                source_ref="/approved/clip.wav",
                modality="audio",
                locator="timestamp:00:18",
                audible="One speaker is talking.",
                transcribed_text="The product costs forty seven dollars.",
                confidence="HIGH",
            )
        ],
        default_content_hash="b" * 64,
    )

    assert len(atomics) == 1
    atomic = atomics[0]

    assert atomic.locator == "timestamp:00:18"
    assert "Modality: AUDIO" in atomic.description
    assert "Audible: One speaker is talking." in atomic.description
    assert "Transcribed: The product costs forty seven dollars." in atomic.description
    assert atomic.evidence_excerpt == ""


def test_video_media_evidence_can_keep_visual_and_audible_separate():
    atomics = atomic_from_media_evidence(
        [
            MediaEvidence(
                source_ref="/approved/clip.mp4",
                modality="video",
                locator="timestamp:01:05",
                visual="A retention graph is shown.",
                audible="The presenter is speaking.",
                transcribed_text="Retention matters after the click.",
                confidence="MEDIUM",
            )
        ]
    )

    assert len(atomics) == 1
    atomic = atomics[0]

    assert "Modality: VIDEO" in atomic.description
    assert "Visual: A retention graph is shown." in atomic.description
    assert "Audible: The presenter is speaking." in atomic.description
    assert "Transcribed: Retention matters after the click." in atomic.description
    assert atomic.locator == "timestamp:01:05"
    assert atomic.evidence_excerpt == ""


def test_media_adapter_fails_closed_on_invalid_or_unlocated_observations():
    atomics = atomic_from_media_evidence(
        [
            MediaEvidence(
                source_ref="",
                modality="image",
                locator="image:whole",
                visual="something",
            ),
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="image",
                locator="",
                visual="something",
            ),
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="unknown",
                locator="image:whole",
                visual="something",
            ),
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="image",
                locator="image:whole",
            ),
        ]
    )

    assert atomics == []


def test_media_atomic_can_persist_through_canonical_finding_seam(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    atomics = atomic_from_media_evidence(
        [
            MediaEvidence(
                source_ref="/approved/photo.png",
                modality="image",
                locator="image:whole",
                visual="A blue package is visible.",
                confidence="HIGH",
            )
        ],
        default_content_hash="c" * 64,
    )

    first = persist_atomic_evidence(
        atomics,
        evidence="/approved/photo.png",
        source="media_test",
        category="visual_research",
        knowledge=knowledge,
        provider="fake_media",
        default_observed_at="2026-09-03T12:00:00+00:00",
    )

    second = persist_atomic_evidence(
        atomics,
        evidence="/approved/photo.png",
        source="media_test",
        category="visual_research",
        knowledge=knowledge,
        provider="fake_media",
        default_observed_at="2026-09-03T12:00:00+00:00",
    )

    assert len(first) == 1
    assert second == []
    assert len(knowledge.findings()) == 1

    finding = first[0]
    assert finding.evidence == "/approved/photo.png"
    assert finding.evidence_locator == "image:whole"
    assert finding.evidence_excerpt == ""
    assert finding.content_hash == "c" * 64
    assert finding.provider == "fake_media"
