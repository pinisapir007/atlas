"""Marketplace -> Cognitive Foundation Bridge (2026-08-14, Cognitive
State Wiring; cleaned up 2026-08-17, ONE BRAIN Root Implementation).
Connects the real, catalog-persisted Marketplace product data
(MarketplaceCatalogStore) to the real, already-built Cognitive layer
(Finding, Claim) -- deliberately not a new semantic engine.

REMOVED (2026-08-17, per the approved ONE BRAIN correction --
docs of the design audit that found and proved this): the original
version of this module also contained `advance_marketplace_opportunity()`
(created `atlas.brain.models.Opportunity` directly), `mark_candidate()`/
`reject_candidate()` (called `Opportunity.transition()` directly), and
`plan_investigation()` (built an unsaved Task off `Opportunity.history`,
which Bridge 1 never populates -- `Opportunity.transition()` has zero
real callers anywhere in this codebase). All four were a second,
unauthorized Opportunity writer/stage-mutator -- confirmed, via direct
audit, to conflict with `opportunity_advance.advance_opportunities_from_
findings()` (Bridge 1), which is qualified and locked as the ONLY real
writer to Opportunity (docs/QUALIFICATION_BUSINESS_OPPORTUNITY_
EVALUATION.md). Never wired into production (CEOBrain.tick() never
imported this module), so nothing live ever broke -- caught before it
shipped.

The real, approved replacement path:

    Marketplace observation
        -> ground_marketplace_product() / claim_derived_economics() [here, unchanged]
        -> a real atlas.brain.models.Investigation
           (atlas.brain.investigations.InvestigationStore)
        -> atlas.brain.investigation_advance.advance_investigations()
           [sense-agnostic -- not Marketplace-specific]
        -> atlas.brain.opportunity_advance.advance_opportunities_from_findings()
           (Bridge 1, unchanged -- the ONLY creator of Opportunity)

This module itself now only ever produces Finding/Claim evidence and
performs read-only identity verification -- it never creates or
mutates an Opportunity, directly or indirectly.

Canonical identity discipline (unchanged): every function here takes a
`canonical_id` parameter -- the reconciled key
MarketplaceCatalogStore.save_records_with_identity()/resolve_canonical()
already produce, never a raw dedupe_key() computed independently.

Observed vs. Derived (unchanged, strict separation):
- OBSERVED FACT: ground_marketplace_product() -- a real Finding quoting
  the record's own real fields, and a Claim (claim_type="observation")
  that merely names what was observed. No judgment.
- DERIVED FACT: claim_derived_economics() -- a real, deterministic
  formula (marketplace_evaluation.economic_signal_score(), UNCHANGED, no
  new scoring logic) over already-observed fields. claim_type="inference"
  -- an explainable computation, not a guess.
- INTERPRETATION: deliberately NOT produced automatically anywhere in
  this module -- that is exactly what atlas.brain.reasoning_claims.
  reason() is for, an explicit, separate, deliberate call.
- UNKNOWN: whatever neither of the above two functions produced.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_evaluation import economic_signal_score
from atlas.brain.marketplace_extraction import MarketplaceProductRecord
from atlas.brain.models import Claim, Finding

MARKETPLACE_OPPORTUNITY_CATEGORY = "affiliate"  # the real, existing business-model tag this codebase already uses for Digistore24-sourced work -- not a new taxonomy value


def ground_marketplace_product(
    record: MarketplaceProductRecord, canonical_id: str, knowledge: KnowledgeBase
) -> Claim | None:
    """OBSERVED FACT. Idempotent: if a Claim already grounds this
    canonical_id (predicate="observed_as"), returns None rather than
    creating a duplicate Finding/Claim pair on every re-observation.
    `evidence` is the record's own real source_url -- never fabricated."""
    if knowledge.claims(subject_id=canonical_id, predicate="observed_as"):
        return None

    finding = Finding(
        source="marketplace_catalog",
        category=MARKETPLACE_OPPORTUNITY_CATEGORY,
        description=(
            f"Digistore24 Marketplace listing: {record.product_name} "
            f"(vendor={record.vendor or 'unknown'}), price=${record.price}, "
            f"commission={record.commission_pct}%, category={record.category or 'unknown'}"
        ),
        evidence=record.source_url,
        provider="digistore24",
        subject=canonical_id,
        # evidence_role (2026-08-17, ONE BRAIN Evidence Role Gate):
        # "aggregated_report" -- this one Finding genuinely bundles
        # vendor-set fields (name/price/commission/description) with
        # platform-computed fields (conversion/cancel/profit stats), two
        # real, different possible claimants -- never one. claimant stays
        # "" deliberately (the ONE BRAIN Claimant Attribution audit's
        # locked conclusion: this artifact is MIXED, not safe to assign a
        # single claimant to). "aggregated_report" is still safe to trust
        # via origin alone: record.source_url is one real, singular
        # observation event, and Finding-level granularity already caps
        # this Finding's contribution at exactly one independent-source
        # group, no matter how much it internally aggregates.
        evidence_role="aggregated_report",
    )
    knowledge.save_finding(finding)

    claim = Claim(
        subject_id=canonical_id,
        predicate="observed_as",
        object_value=record.product_name,
        evidence_finding_ids=[finding.id],
        source="manual",
        claim_type="observation",
    )
    knowledge.save_claim(claim)
    return claim


def claim_derived_economics(
    record: MarketplaceProductRecord, canonical_id: str, evidence_finding_ids: list[str], knowledge: KnowledgeBase
) -> Claim | None:
    """DERIVED FACT. Reuses marketplace_evaluation.economic_signal_score()
    verbatim -- no new formula. Returns None (never a fabricated Claim)
    when the real score itself is None (every component field
    unmeasured), or when already grounded this call (idempotent, same
    discipline as ground_marketplace_product())."""
    if knowledge.claims(subject_id=canonical_id, predicate="economic_signal_score"):
        return None

    signal = economic_signal_score(record)
    if signal["score"] is None:
        return None

    claim = Claim(
        subject_id=canonical_id,
        predicate="economic_signal_score",
        object_value=f"{signal['score']:.3f}",
        evidence_finding_ids=list(evidence_finding_ids),
        source="manual",
        claim_type="inference",
    )
    knowledge.save_claim(claim)
    return claim


def verify_revisit_identity(
    expected_canonical_id: str, observed_record: MarketplaceProductRecord, catalog: MarketplaceCatalogStore
) -> bool:
    """The Revisit Contract's identity check: content identity, never
    page number/viewport/visual position. Re-resolves the freshly
    observed record's canonical identity (via
    MarketplaceCatalogStore.resolve_canonical(), read-only) and compares
    it to what was expected. A mismatch returns False -- the caller is
    expected to fail closed on that, never assume it found the right
    product anyway."""
    return catalog.resolve_canonical(observed_record) == expected_canonical_id
