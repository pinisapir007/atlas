"""Research Mission -> qualified Knowledge Source routing bridge.

This bridge processes concrete sources already attached to a durable
ResearchMission.

It does NOT discover sources, approve domains/paths, create Tasks,
create Decisions/Opportunities, or perform any commercial action.

Supported here:
- Browser
- Document
- PDF
- Image
- Audio
- local Video

YouTube is deliberately NOT processed here. The qualified YouTube path
uses timestamped VideoEvidence and remains a separate orchestration seam.

Every invocation processes at most one eligible pending source.
"""

from atlas.brain.audio_plugin import (
    PathNotApprovedError as AudioPathNotApprovedError,
)
from atlas.brain.browser_plugin import DomainNotApprovedError
from atlas.brain.document_plugin import (
    PathNotApprovedError as DocumentPathNotApprovedError,
)
from atlas.brain.feature_flags import research_mission_enabled
from atlas.brain.image_plugin import (
    PathNotApprovedError as ImagePathNotApprovedError,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_registry import select_plugin
from atlas.brain.knowledge_source_research import (
    AtomicTextSourceUnsupported,
    EvidenceQualityRejected,
    MediaEvidenceSourceMismatch,
    SubjectAttributionUnverified,
    collect_atomic_evidence_from_source,
)
from atlas.brain.models import now
from atlas.brain.pdf_plugin import PDFPathNotApprovedError
from atlas.brain.research_missions import (
    ResearchMissionSource,
    ResearchMissionStore,
)
from atlas.brain.video_plugin import (
    PathNotApprovedError as VideoPathNotApprovedError,
)
from atlas.integrations.base import AIProvider


MAX_SOURCES_PER_CALL = 1

_PERMANENT_REJECTIONS = (
    DomainNotApprovedError,
    DocumentPathNotApprovedError,
    PDFPathNotApprovedError,
    ImagePathNotApprovedError,
    AudioPathNotApprovedError,
    VideoPathNotApprovedError,
    EvidenceQualityRejected,
    SubjectAttributionUnverified,
    AtomicTextSourceUnsupported,
    MediaEvidenceSourceMismatch,
)


def _save_rejected(
    store: ResearchMissionStore,
    source: ResearchMissionSource,
    reason: str,
) -> None:
    source.status = "rejected"
    source.last_error = reason[:1000]
    source.updated_at = now()
    store.save_source(source)


def _save_retryable_failure(
    store: ResearchMissionStore,
    source: ResearchMissionSource,
    max_attempts: int,
    reason: str,
) -> None:
    source.last_error = reason[:1000]
    source.updated_at = now()

    if source.attempts >= max_attempts:
        source.status = "failed_exhausted"
    else:
        source.status = "pending"

    store.save_source(source)


def advance_research_mission_sources(
    store: ResearchMissionStore,
    knowledge: KnowledgeBase,
    *,
    ai_provider: AIProvider | None = None,
) -> list[ResearchMissionSource]:
    """Process at most one eligible pending source.

    Feature flag disabled -> strict no-op.

    Routing is determined only by select_plugin(source_ref). source_kind is
    informational and is never trusted for dispatch.

    YouTube remains pending for the separately-qualified YouTube bridge and
    does not consume an attempt here.

    Successful collection with >=1 returned Finding:
        pending -> processed

    Real source was readable but yielded zero verified atomic Findings:
        pending -> rejected
    because "processed" must never imply evidence exists when none does.

    Permanent safety/epistemic rejection:
        pending -> rejected

    Other real backend/provider failures:
        pending -> pending while retry budget remains
        pending -> failed_exhausted once max_attempts_per_source is reached
    """
    if not research_mission_enabled():
        return []

    handled: list[ResearchMissionSource] = []

    missions = sorted(
        store.active_missions(),
        key=lambda mission: (
            mission.created_at,
            mission.id,
        ),
    )

    for mission in missions:
        pending = sorted(
            store.pending_sources(mission.id),
            key=lambda source: (
                source.created_at,
                source.id,
            ),
        )

        for source in pending:
            if len(handled) >= MAX_SOURCES_PER_CALL:
                return handled

            # Structural routing check happens before an attempt is consumed.
            try:
                plugin = select_plugin(source.source_ref)
            except ValueError as exc:
                source.attempts += 1
                _save_rejected(
                    store,
                    source,
                    f"unsupported source_ref: {exc}",
                )
                handled.append(store.get_source(source.id))
                return handled

            # YouTube has a separately-qualified timestamped evidence path.
            # Never degrade it into generic whole-source/media collection.
            if plugin.name == "youtube":
                continue

            # Persist the consumed attempt BEFORE the external/source call.
            # If the real process is interrupted, durable state still records
            # that an attempt began rather than silently forgetting it.
            source.attempts += 1
            source.updated_at = now()
            store.save_source(source)

            try:
                findings = collect_atomic_evidence_from_source(
                    source_ref=source.source_ref,
                    category=source.category,
                    source="research_mission",
                    task_description=source.task_description,
                    knowledge=knowledge,
                    ai_provider=ai_provider,
                    provider=plugin.name,
                )

            except _PERMANENT_REJECTIONS as exc:
                _save_rejected(
                    store,
                    source,
                    f"{type(exc).__name__}: {exc}",
                )

            except Exception as exc:
                _save_retryable_failure(
                    store,
                    source,
                    mission.max_attempts_per_source,
                    f"{type(exc).__name__}: {exc}",
                )

            else:
                if not findings:
                    _save_rejected(
                        store,
                        source,
                        "source produced zero verified atomic Findings",
                    )
                else:
                    source.status = "processed"
                    source.finding_ids = sorted(
                        {
                            finding.id
                            for finding in findings
                        }
                    )
                    source.last_error = ""
                    source.updated_at = now()
                    store.save_source(source)

            handled.append(
                store.get_source(source.id)
            )
            return handled

    return handled
