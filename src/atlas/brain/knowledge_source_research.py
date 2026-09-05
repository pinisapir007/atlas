"""Knowledge Source Research V1 (2026-08-06) — the generalized
successor to atlas.brain.browser_research.collect_evidence_from_url:
the same real "observe a real source, produce exactly one real,
durable Finding" mechanism, now dispatching by real plugin
(knowledge_source_registry.select_plugin) instead of taking a single
BrowserObserver directly, and now gated by real Evidence Validation
before a Finding is ever saved.

browser_research.py is untouched and stays real/valid for the
narrower "browser only, no quality gate" case; this module is the
preferred entry point going forward, for any real registered source —
web today, and a future document/video/social source with zero change
to this function.

Never infers category/subject/market from content -- same discipline
browser_research.py already established. Never touches the Decision
Engine, Finding, or KnowledgeBase's own shape -- a Finding produced
here is picked up automatically on the next tick, same as any other.
"""

from atlas.brain.browser_research import _real_description
from atlas.brain.atomic_evidence import (
    atomic_from_media_evidence,
    persist_atomic_evidence,
)
from atlas.brain.atomic_text_extraction import (
    MAX_ATOMICS_PER_CHUNK,
    MAX_CHUNK_CHARS,
    extract_atomic_evidence_from_text,
)
from atlas.brain.evidence_role_classification import UNKNOWN as ROLE_UNKNOWN
from atlas.brain.evidence_role_classification import classify_evidence_role
from atlas.brain.evidence_validation import assess_observation_quality
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_registry import select_plugin
from atlas.brain.models import Finding
from atlas.brain.observation_metadata import (
    observation_content_hash,
    observation_observed_at,
)
from atlas.brain.subject_verification import SubjectMatch, verify_subject_match
from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider, KnowledgeSourcePlugin, PageObservation


class EvidenceQualityRejected(ValueError):
    """Raised when a real observation was successfully read but
    failed evidence-quality validation (a real error, too little real
    text, or a real AI judgment that it doesn't address the task) —
    never silently turned into a low-quality Finding."""


class SubjectAttributionUnverified(ValueError):
    """Raised when a real observation passed quality/relevance checks
    but could not be confirmed (via subject_verification.
    verify_subject_match()) to genuinely be about the specific
    `subject` requested (2026-08-17, ONE BRAIN Root Implementation --
    the fix for the confirmed return-path defect). Deliberately never
    caught here to fall back to saving a category-general
    (subject="") Finding instead: a prior design round proved that
    still contaminates category-level confidence_score()/decide()
    (neither filters by subject), so the only real fail-closed choice
    is the same one EvidenceQualityRejected already establishes --
    raise loudly, save nothing."""



class AtomicTextSourceUnsupported(ValueError):
    """Raised when a source has neither grounded raw text nor a native
    evidence-honest atomic media path."""


class MediaEvidenceSourceMismatch(ValueError):
    """Raised when a media plugin returns evidence for a different or
    ambiguous source instead of the exact media item it observed."""


def _observe_validated_source(
    source_ref: str,
    task_description: str,
    subject: str = "",
    extract: dict[str, str] | None = None,
    ai_provider: AIProvider | None = None,
    *,
    require_grounded_text: bool = False,
    plugin_override: KnowledgeSourcePlugin | None = None,
) -> tuple[KnowledgeSourcePlugin, PageObservation, str]:
    """One shared source gate for both legacy and atomic collection.

    Order is deliberate:
    select real source plugin -> optional capability gate -> observe real
    source -> evidence quality -> subject attribution -> evidence role.

    No Finding is created here. Both persistence paths therefore consume
    the exact same validated observation and cannot drift into two
    different definitions of trustworthy evidence.
    """
    plugin = (
        plugin_override
        if plugin_override is not None
        else select_plugin(source_ref)
    )

    if require_grounded_text and not getattr(plugin, "raw_text_grounded", False):
        raise AtomicTextSourceUnsupported(
            f"plugin {plugin.name!r} does not guarantee real raw text; "
            "use its source-specific grounded evidence path instead"
        )

    observation = plugin.observe(source_ref, extract=extract)

    quality = assess_observation_quality(
        observation,
        task_description,
        ai_provider=ai_provider,
    )
    if not quality.passed:
        raise EvidenceQualityRejected(
            f"real observation of {source_ref!r} (via {plugin.name!r}) "
            f"failed evidence quality: {quality.reason}"
        )

    if subject:
        match = verify_subject_match(
            observation,
            subject,
            ai_provider=ai_provider,
        )
        if match != SubjectMatch.VERIFIED_SAME:
            raise SubjectAttributionUnverified(
                f"real observation of {source_ref!r} (via {plugin.name!r}) "
                f"could not be confirmed to be about the requested subject "
                f"{subject!r} (attribution result: {match})"
            )

    role = classify_evidence_role(
        observation,
        requested_subject=subject,
        ai_provider=ai_provider,
    )
    evidence_role = "" if role == ROLE_UNKNOWN else role

    return plugin, observation, evidence_role


def _media_sensor_summary(media_items) -> str:
    """Textual representation of already-produced media sensor observations.

    This is explicitly NOT raw/verbatim source text. It exists only so
    brain-level relevance/attribution gates can reason over what the
    multimodal sensor reported without pretending the report itself is
    primary-source text.
    """
    blocks: list[str] = []

    for item in media_items:
        parts = [
            f"modality={item.modality.strip()}",
            f"locator={item.locator.strip()}",
        ]

        if item.visual.strip():
            parts.append(f"visual={item.visual.strip()}")
        if item.audible.strip():
            parts.append(f"audible={item.audible.strip()}")
        if item.transcribed_text.strip():
            parts.append(
                f"transcribed_text={item.transcribed_text.strip()}"
            )
        if item.confidence.strip():
            parts.append(f"confidence={item.confidence.strip()}")

        blocks.append(" | ".join(parts))

    return "\n".join(blocks).strip()


def _validate_media_evidence(
    media_items,
    *,
    task_description: str,
    subject: str,
    ai_provider: AIProvider | None,
) -> None:
    """Brain-level gates for multimodal sensor evidence.

    Never routes Gemini-produced media interpretation through the raw-text
    PageObservation validators. Relevance and subject attribution are
    judged explicitly from SENSOR OBSERVATIONS, while evidence role is
    deliberately left unknown rather than guessed.
    """
    summary = _media_sensor_summary(media_items)

    if not summary:
        raise EvidenceQualityRejected(
            "native media observation contained no usable sensor evidence"
        )

    provider = (
        ai_provider
        if ai_provider is not None
        else get_ai_provider()
    )

    relevance_prompt = (
        f"A real research task needs to be answered: "
        f"{task_description}\n\n"
        "Below are multimodal SENSOR OBSERVATIONS produced from one real "
        "image/audio/video source. They are not verbatim raw source text "
        "and must not be treated as exact quotations:\n\n"
        f"{summary[:6000]}\n\n"
        "Based ONLY on these sensor observations, do they genuinely provide "
        "evidence toward the task? Answer no if the available observation "
        "is too weak, ambiguous, or unrelated."
    )

    relevance = provider.complete_structured(
        relevance_prompt,
        {
            "relevant": "the single word yes or no",
            "reason": "one honest sentence explaining the judgment",
        },
    )

    if not (
        relevance.get("relevant", "")
        .strip()
        .lower()
        .startswith("y")
    ):
        raise EvidenceQualityRejected(
            "media sensor evidence failed task relevance: "
            f"{relevance.get('reason', '')}"
        )

    if not subject:
        return

    subject_prompt = (
        f"We requested evidence specifically about this real-world "
        f"subject: {subject!r}\n\n"
        "Below are multimodal SENSOR OBSERVATIONS produced from one real "
        "media source. They are AI interpretations of the source, not "
        "verbatim raw text:\n\n"
        f"{summary[:6000]}\n\n"
        "Do these observations provide clear evidence that the media is "
        "about that EXACT subject? Answer 'same' only with clear support; "
        "'different' only with clear evidence of another specific entity; "
        "otherwise answer 'unknown'. Never infer identity merely because "
        "the requested name is plausible."
    )

    result = provider.complete_structured(
        subject_prompt,
        {
            "verdict": "exactly one word: same, different, or unknown",
            "reason": "one honest sentence explaining the judgment",
        },
    )

    verdict = result.get("verdict", "").strip().lower()

    if not verdict.startswith("same"):
        attribution = (
            SubjectMatch.VERIFIED_DIFFERENT
            if verdict.startswith("different")
            else SubjectMatch.UNKNOWN
        )
        raise SubjectAttributionUnverified(
            f"media evidence could not be confirmed to be about "
            f"{subject!r} (attribution result: {attribution})"
        )


def collect_evidence_from_source(
    source_ref: str,
    category: str,
    source: str,
    task_description: str,
    knowledge: KnowledgeBase,
    subject: str = "",
    market: str = "",
    extract: dict[str, str] | None = None,
    ai_provider: AIProvider | None = None,
) -> Finding:
    """Dispatches to the real registered plugin for `source_ref`
    (raises ValueError if none can handle it), observes it for real,
    validates the real result against `task_description` (raises
    EvidenceQualityRejected if it doesn't pass), and records exactly
    one real, durable Finding. Whatever real error the selected
    plugin raises (not approved, not found, a real backend failure)
    propagates unchanged -- never caught here to fabricate a fallback
    result."""
    _, observation, evidence_role = _observe_validated_source(
        source_ref=source_ref,
        task_description=task_description,
        subject=subject,
        extract=extract,
        ai_provider=ai_provider,
    )

    finding = Finding(
        source=source,
        category=category,
        description=_real_description(observation),
        # evidence_provenance.py (2026-08-17, ONE BRAIN Evidence
        # Provenance): the real, final observed identifier
        # (observation.url -- a real post-redirect URL for web sources,
        # a real resolved local path for document/image/audio/video
        # sources), never the originally-requested `source_ref` --
        # every real KnowledgeSourcePlugin already populates this
        # meaningfully (verified: Browser/Document/Image/Audio/Video/
        # YouTube all set a real, final `url`).
        evidence=observation.url,
        subject=subject,
        market=market,
        evidence_role=evidence_role,
        observed_at=observation_observed_at(observation),
        content_hash=observation_content_hash(observation),
    )
    knowledge.save_finding(finding)
    return finding



def collect_atomic_evidence_from_source(
    source_ref: str,
    category: str,
    source: str,
    task_description: str,
    knowledge: KnowledgeBase,
    subject: str = "",
    market: str = "",
    extract: dict[str, str] | None = None,
    ai_provider: AIProvider | None = None,
    *,
    plugin_override: KnowledgeSourcePlugin | None = None,
    provider: str = "",
    max_chunk_chars: int = MAX_CHUNK_CHARS,
    max_atomics_per_chunk: int = MAX_ATOMICS_PER_CHUNK,
) -> list[Finding]:
    """Ground one real raw-text source into zero-or-many durable Findings.

    This is additive: collect_evidence_from_source() remains the existing
    one-source -> one-Finding API.

    Grounded raw-text plugins (Browser, Document, PDF) use exact-quote
    verification. Native local media plugins (Image, Audio, Video) use
    their evidence-honest `observe_evidence()` contract and the shared
    MediaEvidence -> AtomicEvidence seam. YouTube remains on its separately
    qualified timestamped VideoEvidence path rather than being degraded to
    whole-video generic media evidence.

    Every atomic statement must survive exact-quote verification in
    atomic_text_extraction before it can reach KnowledgeBase. Zero valid
    atomic observations returns [] honestly -- never falls back to an
    invented summary Finding.
    """
    # Stage 7 Observation: choose the evidence-honest path by source
    # capability. Raw text uses exact quote verification. Native media
    # uses MediaEvidence and must never pretend Gemini interpretation is
    # character-for-character grounded source text.
    plugin = (
        plugin_override
        if plugin_override is not None
        else select_plugin(source_ref)
    )

    if not getattr(plugin, "raw_text_grounded", False):
        observe_evidence = getattr(plugin, "observe_evidence", None)

        if not callable(observe_evidence):
            raise AtomicTextSourceUnsupported(
                f"plugin {plugin.name!r} does not guarantee real raw text "
                "and has no native atomic media evidence path"
            )

        media_items = observe_evidence(source_ref)

        if not media_items:
            return []

        source_refs = {
            item.source_ref.strip()
            for item in media_items
            if item.source_ref.strip()
        }

        # Fail closed: one collection call is for exactly one real source.
        if len(source_refs) != 1:
            raise MediaEvidenceSourceMismatch(
                f"plugin {plugin.name!r} returned evidence for "
                f"{len(source_refs)} distinct/nonempty sources"
            )

        media_source_ref = next(iter(source_refs))

        _validate_media_evidence(
            media_items,
            task_description=task_description,
            subject=subject,
            ai_provider=ai_provider,
        )

        atomics = atomic_from_media_evidence(media_items)

        if not atomics:
            return []

        return persist_atomic_evidence(
            atomics,
            evidence=media_source_ref,
            source=source,
            category=category,
            knowledge=knowledge,
            provider=provider,
            subject=subject,
            market=market,
        )

    _, observation, evidence_role = _observe_validated_source(
        source_ref=source_ref,
        task_description=task_description,
        subject=subject,
        extract=extract,
        ai_provider=ai_provider,
        require_grounded_text=True,
        plugin_override=plugin,
    )

    atomic_provider = (
        ai_provider
        if ai_provider is not None
        else get_ai_provider()
    )

    atomics = []

    if observation.text_segments:
        # Preserve real source-native structure (e.g. PDF pages).
        # Each segment is atomized independently, so a quote can never
        # accidentally cross a page/section boundary.
        for segment in observation.text_segments:
            atomics.extend(
                extract_atomic_evidence_from_text(
                    segment.text,
                    task_description,
                    atomic_provider,
                    max_chunk_chars=max_chunk_chars,
                    max_atomics_per_chunk=max_atomics_per_chunk,
                    locator_prefix=segment.locator_prefix,
                )
            )
    else:
        atomics = extract_atomic_evidence_from_text(
            observation.text_content,
            task_description,
            atomic_provider,
            max_chunk_chars=max_chunk_chars,
            max_atomics_per_chunk=max_atomics_per_chunk,
        )

    return persist_atomic_evidence(
        atomics,
        evidence=observation.url,
        source=source,
        category=category,
        knowledge=knowledge,
        provider=provider,
        subject=subject,
        market=market,
        default_evidence_role=evidence_role,
        default_observed_at=observation_observed_at(observation),
        default_content_hash=observation_content_hash(observation),
    )
