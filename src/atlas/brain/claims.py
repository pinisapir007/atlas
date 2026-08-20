"""Pure, read-only derivation functions for Claim (2026-08-15, Cognitive
Foundation) — the same "currentness computed fresh, never a stored field
that can go stale" discipline already established for
SuccessLaw.evidence_finding_ids (bool-checked, never a separately-stored
status) and Decision (recomputed by decide() every call). Neither function
is called from KnowledgeBase.save_claim() or reason() — both are read-time
views any caller computes on demand from a Claim's own real fields.
"""

from atlas.brain.confidence import SOURCE_SATURATION_SAMPLE
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim


def claim_status(claim: Claim) -> str:
    """Derives an honest epistemic state from three real fields —
    `superseded_by_id`, `contradicted_by_finding_ids`,
    `evidence_finding_ids` — never a fourth, separately-stored status
    field that could drift out of sync with them.

    "insufficient_evidence" (empty evidence_finding_ids, no contradiction)
    is a legitimate, permanent, non-discarded state — a coherent
    hypothesis ATLAS cannot yet confirm is knowledge about what is not
    yet known, not something that disappears. "ambiguous" (both real
    support AND real contradiction present) and "contradicted" (only
    contradiction, no support) are kept structurally distinct from
    "supported" — this function is also the one place naive arithmetic
    ("3 supports minus 1 contradiction = still mostly true") is
    structurally impossible, since contradiction is never subtracted from
    a count, only checked for presence."""
    if claim.superseded_by_id is not None:
        return "superseded"
    if claim.contradicted_by_finding_ids and claim.evidence_finding_ids:
        return "ambiguous"
    if claim.contradicted_by_finding_ids and not claim.evidence_finding_ids:
        return "contradicted"
    if not claim.evidence_finding_ids:
        return "insufficient_evidence"
    return "supported"  # real corroborating evidence exists — never "true", still re-validatable


def claim_confidence(claim: Claim, knowledge: KnowledgeBase) -> float | None:
    """Confidence computed EXCLUSIVELY from this Claim's own
    `evidence_finding_ids` — deliberately NOT
    confidence.source_corroboration_score(), whose category/subject/
    provider-scoped query would pull in every matching Finding in the
    KnowledgeBase, not just the ones actually attached to this Claim. A
    Claim may only gain epistemic support from evidence explicitly linked
    to it (Design Lock invariant, 2026-08-15) — a different, claim-local
    scope than category-level confidence legitimately uses.

    Returns None whenever real contradicting evidence exists
    (`contradicted_by_finding_ids` non-empty) — a numeric score here would
    misleadingly read as "still mostly right despite the disagreement";
    claim_status() is the correct place to learn that, not a discounted
    number. Also None when no real, sourced evidence exists yet (an
    open, unresolved hypothesis) — never a fabricated 0.0.

    Reuses SOURCE_SATURATION_SAMPLE (3 independently-sourced findings =
    full corroboration credit) from confidence.py rather than inventing a
    second saturation constant — same methodology, claim-local scope. An
    honest Finding-count approximation, not a verified independent-source
    check (source_corroboration_score() has this exact same limitation,
    inherited here rather than silently promised away)."""
    if claim.contradicted_by_finding_ids:
        return None
    findings = [knowledge.get_finding(fid) for fid in claim.evidence_finding_ids]
    sourced = [f for f in findings if f.evidence]
    if not sourced:
        return None
    return min(len(sourced) / SOURCE_SATURATION_SAMPLE, 1.0)
