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
from atlas.brain.evidence_role_classification import UNKNOWN as ROLE_UNKNOWN
from atlas.brain.evidence_role_classification import classify_evidence_role
from atlas.brain.evidence_validation import assess_observation_quality
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_registry import select_plugin
from atlas.brain.models import Finding
from atlas.brain.subject_verification import SubjectMatch, verify_subject_match
from atlas.integrations.base import AIProvider


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
    plugin = select_plugin(source_ref)
    observation = plugin.observe(source_ref, extract=extract)

    quality = assess_observation_quality(observation, task_description, ai_provider=ai_provider)
    if not quality.passed:
        raise EvidenceQualityRejected(
            f"real observation of {source_ref!r} (via {plugin.name!r}) failed evidence quality: {quality.reason}"
        )

    # Return-Path Subject Verification (2026-08-17, ONE BRAIN Root
    # Implementation): only runs when the caller requested a concrete
    # subject -- a category-general call (subject="") has nothing to
    # verify attribution against, and stays exactly as backward-
    # compatible as it always was. request-relevance (above) and
    # entity-attribution (here) are two genuinely different questions
    # (a returned page can be perfectly on-task and still be about the
    # wrong real-world entity) -- never merged into one check.
    if subject:
        match = verify_subject_match(observation, subject, ai_provider=ai_provider)
        if match != SubjectMatch.VERIFIED_SAME:
            raise SubjectAttributionUnverified(
                f"real observation of {source_ref!r} (via {plugin.name!r}) could not be confirmed to be "
                f"about the requested subject {subject!r} (attribution result: {match})"
            )

    # Evidence Role Classification (2026-08-17, ONE BRAIN Web Evidence
    # Role Classification): the Brain (not the plugin/sensor that
    # produced `observation`) decides what kind of relationship this
    # artifact has to its real-world source -- the exact same classifier
    # browser_research.collect_evidence_from_url() uses, no local/
    # duplicated role logic here. "unknown" translates to Finding.
    # evidence_role="" -- the single, already-established honest-empty
    # convention.
    role = classify_evidence_role(observation, requested_subject=subject, ai_provider=ai_provider)
    evidence_role = "" if role == ROLE_UNKNOWN else role

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
    )
    knowledge.save_finding(finding)
    return finding
