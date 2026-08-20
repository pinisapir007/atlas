"""ATLAS <-> BrowserObserver Connection V1 (2026-08-06).

The one real function this module exists for: turn a real, allowed
browser observation into a real, durable Finding — the exact same
shape `atlas brain finding add` already produces by hand, just
automated. Deliberately does not touch the Decision Engine, Finding,
or KnowledgeBase in any way: decide()/confidence_score()/
opportunity_ranking already read knowledge.findings() fresh every
call, so a Finding created here is picked up automatically on the
very next tick, with zero additional wiring — the entire point of
reusing the existing model instead of inventing a new one.

Never infers `category`/`subject`/`market` from the page content —
all three are supplied explicitly by the caller (the real research
task that triggered this observation), the same "never guessed,
always '' unless the source states it" discipline Finding.subject/
market already established. This module only ever describes WHERE
the evidence came from (a real URL) and WHAT was actually read
(real, raw page text) — it never decides what the evidence means.
"""

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.brain.evidence_role_classification import UNKNOWN as ROLE_UNKNOWN
from atlas.brain.evidence_role_classification import classify_evidence_role
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.subject_verification import SubjectMatch, verify_subject_match
from atlas.integrations.base import AIProvider, BrowserObserver, PageObservation

_DESCRIPTION_MAX_CHARS = 500


class DomainNotApprovedError(ValueError):
    """Raised when the real domain in a requested URL is not on the
    real BrowserAllowlist — fail-closed, the same default-deny
    discipline ResourceAllowlist already enforces for local files,
    applied here to the real, public internet."""


class SubjectAttributionUnverified(ValueError):
    """Raised when a real observation could not be confirmed (via
    subject_verification.verify_subject_match()) to genuinely be about
    the specific `subject` requested -- the exact same fail-closed
    contract knowledge_source_research.py's own SubjectAttributionUnverified
    already establishes, mirrored here rather than cross-imported (this
    module has no dependency on that one -- the relationship runs the
    other direction)."""


def collect_evidence_from_url(
    url: str,
    category: str,
    source: str,
    observer: BrowserObserver,
    allowlist: BrowserAllowlist,
    knowledge: KnowledgeBase,
    subject: str = "",
    market: str = "",
    extract: dict[str, str] | None = None,
    ai_provider: AIProvider | None = None,
) -> Finding:
    """Navigates to a real, allowed URL, reads its real content, and
    records exactly one real, durable Finding from it. Raises
    DomainNotApprovedError before ever calling `observer` if the
    domain isn't on the real allowlist — the check happens first, not
    as an afterthought. Raises whatever real error `observer.observe()`
    raises on an unrecoverable failure (page unreachable, timeout) —
    never records a Finding from a failed or partial observation.

    Required order (2026-08-17, ONE BRAIN Web Evidence Role
    Classification): observe -> verify subject (only when `subject` is
    given, mirroring knowledge_source_research.collect_evidence_from_
    source()'s exact contract) -> classify evidence role -> create
    Finding -> persist. A wrong-subject observation raises
    SubjectAttributionUnverified and saves nothing -- role is never
    classified for evidence that isn't even confirmed to be about the
    right real-world entity.
    """
    if not allowlist.is_approved(url):
        raise DomainNotApprovedError(f"domain not approved for autonomous browsing: {url!r}")

    # verify_target (2026-08-13, M1 Marketplace Discovery Safety Wiring):
    # passed through to a real BrowserObserver implementation that honors
    # it (e.g. BrowserUseObserver) so a redirect is caught *before* page
    # text/screenshot are ever read -- not just before the result is
    # trusted afterward. The post-observe re-check below is kept as
    # defense-in-depth for any BrowserObserver implementation that doesn't
    # honor verify_target (the Protocol parameter is optional) -- belt and
    # suspenders, not redundant duplication.
    observation = observer.observe(url, extract=extract, verify_target=allowlist.is_approved)

    if not allowlist.is_approved(observation.url):
        raise DomainNotApprovedError(
            f"real destination after navigation/redirect is not approved: {observation.url!r} (requested {url!r})"
        )

    if subject:
        match = verify_subject_match(observation, subject, ai_provider=ai_provider)
        if match != SubjectMatch.VERIFIED_SAME:
            raise SubjectAttributionUnverified(
                f"real observation of {observation.url!r} could not be confirmed to be about the requested "
                f"subject {subject!r} (attribution result: {match})"
            )

    # Evidence Role Classification (2026-08-17, ONE BRAIN Web Evidence
    # Role Classification): the Brain (not this sensor) decides what
    # kind of relationship this artifact has to its real-world source.
    # "unknown" translates to Finding.evidence_role="" -- the single,
    # already-established honest-empty convention every other Finding
    # field already uses (never a second spelling of "unknown" on this
    # field).
    role = classify_evidence_role(observation, requested_subject=subject, ai_provider=ai_provider)
    evidence_role = "" if role == ROLE_UNKNOWN else role

    finding = Finding(
        source=source,
        category=category,
        description=_real_description(observation),
        # evidence_provenance.py (2026-08-17, ONE BRAIN Evidence
        # Provenance): the real, FINAL observed URL (observation.url,
        # already re-verified against the allowlist above), never the
        # originally-requested `url` -- a redirect landing on a
        # different real page must never be recorded under the URL
        # that was merely asked for.
        evidence=observation.url,
        subject=subject,
        market=market,
        evidence_role=evidence_role,
    )
    knowledge.save_finding(finding)
    return finding


def _real_description(observation: PageObservation) -> str:
    """The real, raw text actually read from the page — truncated for
    storage size, never summarized or rewritten by this layer. If the
    caller requested specific structured fields (`extract`), those real
    values are included first since they're the most targeted real
    evidence available."""
    if observation.structured_data:
        structured = ", ".join(f"{k}: {v}" for k, v in observation.structured_data.items())
        return f"{structured} — {observation.text_content}"[:_DESCRIPTION_MAX_CHARS]
    return observation.text_content[:_DESCRIPTION_MAX_CHARS]
