"""Stage 7 Atomic Evidence Engine — canonical persistence seam.

AtomicEvidence is TRANSIENT extraction output, never a second memory
system. Finding remains ATLAS's one durable evidence/observation unit.

This module solves two Stage 7 requirements:
1. one source may yield many precise Findings;
2. re-reading unchanged evidence must not inflate KnowledgeBase.

Dedup is deliberately exact and evidence-grounded, never semantic
guessing: source + locator + description + source content hash +
business scope must all match.
"""

import hashlib
from dataclasses import dataclass

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.integrations.base import MediaEvidence, VideoEvidence


@dataclass(frozen=True)
class AtomicEvidence:
    """One precise evidence unit extracted from a real source.

    `description` must describe only what the source directly supports.
    `locator` is exact when known (line range/page/timestamp/etc.) and
    empty when not provable. Nothing here is durable until converted
    into a Finding.
    """

    description: str
    locator: str = ""
    evidence_excerpt: str = ""
    claimant: str = ""
    evidence_role: str = ""
    observed_at: str = ""
    content_hash: str = ""


def _same_atomic_finding(
    finding: Finding,
    *,
    evidence: str,
    atomic: AtomicEvidence,
    category: str,
    provider: str,
    subject: str,
    market: str,
) -> bool:
    """Exact idempotency identity — never fuzzy/semantic dedup."""
    return (
        finding.evidence == evidence
        and finding.evidence_locator == atomic.locator
        and (
            finding.evidence_excerpt == atomic.evidence_excerpt
            if atomic.evidence_excerpt
            else finding.description == atomic.description
        )
        and finding.content_hash == atomic.content_hash
        and finding.category == category
        and finding.provider == provider
        and finding.subject == subject
        and finding.market == market
    )


def persist_atomic_evidence(
    atomics: list[AtomicEvidence],
    *,
    evidence: str,
    source: str,
    category: str,
    knowledge: KnowledgeBase,
    provider: str = "",
    subject: str = "",
    market: str = "",
    default_evidence_role: str = "",
    default_observed_at: str = "",
    default_content_hash: str = "",
) -> list[Finding]:
    """Persist new atomic evidence as canonical Findings.

    Repeated identical extraction is idempotent. Different source
    content hashes remain separate observations deliberately: a changed
    source is longitudinal evidence, not a duplicate to erase.
    """
    existing = knowledge.findings(category=category)
    created: list[Finding] = []

    for atomic in atomics:
        description = atomic.description.strip()
        if not description:
            continue

        normalized = AtomicEvidence(
            description=description,
            locator=atomic.locator.strip(),
            evidence_excerpt=atomic.evidence_excerpt.strip(),
            claimant=atomic.claimant.strip(),
            evidence_role=(atomic.evidence_role or default_evidence_role).strip(),
            observed_at=(atomic.observed_at or default_observed_at).strip(),
            content_hash=(atomic.content_hash or default_content_hash).strip(),
        )

        if any(
            _same_atomic_finding(
                finding,
                evidence=evidence,
                atomic=normalized,
                category=category,
                provider=provider,
                subject=subject,
                market=market,
            )
            for finding in [*existing, *created]
        ):
            continue

        finding = Finding(
            source=source,
            category=category,
            description=normalized.description,
            evidence=evidence,
            provider=provider,
            subject=subject,
            market=market,
            claimant=normalized.claimant,
            evidence_role=normalized.evidence_role,
            observed_at=normalized.observed_at,
            evidence_locator=normalized.locator,
            evidence_excerpt=normalized.evidence_excerpt,
            content_hash=normalized.content_hash,
        )
        knowledge.save_finding(finding)
        created.append(finding)

    return created


def _video_evidence_content_hash(item: VideoEvidence) -> str:
    """Stable identity for one real timestamped video observation."""
    payload = "\n".join(
        [
            item.source_url.strip(),
            item.timestamp.strip(),
            item.spoken.strip(),
            item.visual.strip(),
            item.evidence_type.strip().upper(),
            item.confidence.strip().upper(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_from_video_evidence(
    evidence_items: list[VideoEvidence],
) -> list[AtomicEvidence]:
    """Normalize timestamped VideoEvidence into the common atomic seam.

    Video speech/visual descriptions are preserved as observation data,
    but deliberately NOT promoted to `evidence_excerpt`: unlike grounded
    PDF/text extraction, we have not proved a character-for-character
    transcript against raw media.

    No claimant/evidence-role is guessed here.
    """
    atomics: list[AtomicEvidence] = []

    for item in evidence_items:
        source_url = item.source_url.strip()
        timestamp = item.timestamp.strip()
        spoken = item.spoken.strip()
        visual = item.visual.strip()
        evidence_type = item.evidence_type.strip().upper()
        confidence = item.confidence.strip().upper()

        # Fail closed: a promotable video observation needs a real source,
        # a real locator, and actual audio and/or visual evidence.
        if not source_url or not timestamp or not (spoken or visual):
            continue

        parts: list[str] = []
        if spoken:
            parts.append(f"Spoken: {spoken}")
        if visual:
            parts.append(f"Visual: {visual}")
        if evidence_type:
            parts.append(f"Evidence type: {evidence_type}")
        if confidence:
            parts.append(f"Confidence: {confidence}")

        atomics.append(
            AtomicEvidence(
                description=" | ".join(parts),
                locator=f"timestamp:{timestamp}",
                content_hash=_video_evidence_content_hash(item),
            )
        )

    return atomics


def atomic_from_media_evidence(
    evidence_items: list[MediaEvidence],
    *,
    default_content_hash: str = "",
) -> list[AtomicEvidence]:
    """Normalize evidence-honest multimodal observations.

    Unlike grounded text/PDF/Web, media observations do NOT populate
    `evidence_excerpt`, because Gemini-produced visual/audio/transcription
    descriptions have not been independently verified character-for-
    character against the underlying pixels/audio waveform.

    Local source content identity should be supplied by the caller using
    the SHA-256 of the real media bytes whenever available.
    """
    atomics: list[AtomicEvidence] = []

    for item in evidence_items:
        source_ref = item.source_ref.strip()
        modality = item.modality.strip().lower()
        locator = item.locator.strip()
        visual = item.visual.strip()
        audible = item.audible.strip()
        transcribed = item.transcribed_text.strip()
        confidence = item.confidence.strip().upper()

        if modality not in {"image", "audio", "video"}:
            continue

        # Fail closed: no source, no locator, or no actual observed
        # content means there is no promotable evidence unit.
        if (
            not source_ref
            or not locator
            or not (visual or audible or transcribed)
        ):
            continue

        parts: list[str] = [f"Modality: {modality.upper()}"]

        if visual:
            parts.append(f"Visual: {visual}")
        if audible:
            parts.append(f"Audible: {audible}")
        if transcribed:
            parts.append(f"Transcribed: {transcribed}")
        if confidence:
            parts.append(f"Confidence: {confidence}")

        atomics.append(
            AtomicEvidence(
                description=" | ".join(parts),
                locator=locator,
                evidence_excerpt="",
                observed_at=item.observed_at.strip(),
                content_hash=(
                    item.content_hash or default_content_hash
                ).strip(),
            )
        )

    return atomics
