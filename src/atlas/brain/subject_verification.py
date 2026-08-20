"""Return-Path Subject Verification (2026-08-17, ONE BRAIN Root
Implementation) -- the fix for the confirmed root defect: a returned
observation was previously trusted as being "about" whatever subject
the caller requested, with no check that the actual content supports
that attribution. Sense-agnostic by construction: operates only on
PageObservation (the same generic result every KnowledgeSourcePlugin --
Browser/Document/Image/Audio/Video/YouTube, and any future plugin --
already returns through knowledge_source_research.collect_evidence_
from_source()), never on anything sensor-specific. The Brain (this
module, called from collect_evidence_from_source(), never from inside
any plugin) owns the attribution decision -- sensors only ever extract
raw observations.

Three-state result, deliberately not bool (Design audit finding,
2026-08-17): VERIFIED_DIFFERENT ("real evidence this is a distinct,
specific, other entity") and UNKNOWN ("not enough signal to decide
either way") are two different epistemic claims, even though both
currently lead to the same fail-closed action in
knowledge_source_research.py -- collapsing them into one boolean would
discard that distinction for any future caller/audit that might need
it.

Explicit anti-pattern (locked, do not violate): "the requested subject
name appears somewhere in the text" is NOT, by itself, sufficient
evidence of VERIFIED_SAME -- a deliberately cloned/scam page can state
the exact same product name. This module does not claim to solve that;
it is one honest, real, content-based gate among several layered
defenses (see docs -- source-independence/corroboration remain the
other, separate layers), never a claim of absolute certainty.
"""

from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider, PageObservation


class SubjectMatch:
    """The three-state result vocabulary -- plain string constants (the
    same open-but-documented convention Finding.category/Claim.predicate
    already use), not an enum class, so callers can compare/log/persist
    them exactly like every other string-typed state in this codebase."""

    VERIFIED_SAME = "verified_same"
    VERIFIED_DIFFERENT = "verified_different"
    UNKNOWN = "unknown"


def verify_subject_match(
    observation: PageObservation,
    requested_subject: str,
    ai_provider: AIProvider | None = None,
) -> str:
    """Real, AI-judged (never string-containment/fuzzy) check of whether
    `observation`'s real title/text_content genuinely describes
    `requested_subject` as a specific, identifiable real-world entity --
    not merely a similarly-named or generically-related one. Reuses the
    exact AIProvider.complete_structured seam
    evidence_validation.assess_observation_quality() already establishes
    -- a second, distinct question (request-relevance is a different
    axis, unchanged there), not a duplicated mechanism.

    Returns SubjectMatch.UNKNOWN whenever the AI's own answer isn't a
    clear same/different -- never guessed toward VERIFIED_SAME merely
    because nothing contradicts it (UNKNOWN is preferred to false
    certainty, per the locked ONE BRAIN principle)."""
    text = (observation.text_content or "").strip()
    title = (observation.title or "").strip()
    combined = f"Title: {title}\n\n{text[:4000]}" if title else text[:4000]

    provider = ai_provider if ai_provider is not None else get_ai_provider()
    prompt = (
        f"We requested independent evidence specifically about this real-world subject: {requested_subject!r}\n\n"
        f"Here is real text actually observed from a real source:\n{combined}\n\n"
        "Does this text genuinely describe/refer to that EXACT real-world subject -- not merely a "
        "similarly-named, related, or different entity? Only answer 'same' if there is clear, specific "
        "textual evidence it is the same real-world entity. Answer 'different' only if there is clear "
        "evidence it is a distinct, different, identifiable entity. Otherwise answer 'unknown' -- "
        "unknown is the correct, preferred answer whenever you are not genuinely certain."
    )
    fields = {
        "verdict": "exactly one word: same, different, or unknown",
        "reason": "one honest sentence explaining the judgment",
    }
    result = provider.complete_structured(prompt, fields)
    verdict = result.get("verdict", "").strip().lower()

    if verdict.startswith("same"):
        return SubjectMatch.VERIFIED_SAME
    if verdict.startswith("different"):
        return SubjectMatch.VERIFIED_DIFFERENT
    return SubjectMatch.UNKNOWN
