"""Marketplace -> Investigation Bridge (2026-08-17, ONE BRAIN Production
Wiring Validation). Closes the real, confirmed-disconnected arrow: real
Marketplace observation already persists to `MarketplaceCatalogStore`
(via `run_discovery()`, a separate, human-supervised, long-running
live-browser session -- NOT triggered here, and never will be), but
nothing production-wired ever grounded those already-persisted records
into Finding/Claim, or opened a real `Investigation` for a product with
genuine-but-insufficient evidence.

This bridge touches ZERO browser/network/CDP state: it only ever reads
the already-persisted, local-disk catalog and writes Finding/Claim/
Investigation -- the exact same "operate over already-collected
evidence" shape every other `*_advance.py` bridge in `CEOBrain.tick()`
already has (Bridge 1 itself never triggers new research; it only reads
Findings that already exist). Safe to call every tick, unconditionally.

Sense-agnostic Investigation, Marketplace-specific caller (the same
split `ground_marketplace_product()` already established): `Investigation`
itself carries no Marketplace-specific field or subtype -- only this
bridge function knows how to read `MarketplaceCatalogStore`/call
`ground_marketplace_product()`/`claim_derived_economics()`. A future
sense would get its own, equally-thin bridge of this same shape, never
a change to `Investigation` itself.

Never creates Opportunity, Goal, or Task -- Bridge 1
(`opportunity_advance.py`, unchanged) remains the only creator of
Opportunity, once real evidence actually crosses
`decision_engine.MIN_INDEPENDENT_SOURCES`. Idempotent by construction:
`InvestigationStore.by_subject()` is checked before creating, so the
same canonical subject is never given a second Investigation on a later
call/tick.
"""

import dataclasses

from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_cognitive_bridge import (
    MARKETPLACE_OPPORTUNITY_CATEGORY,
    claim_derived_economics,
    ground_marketplace_product,
)
from atlas.brain.marketplace_extraction import MarketplaceProductRecord
from atlas.brain.models import Investigation

_RECORD_FIELD_NAMES = {f.name for f in dataclasses.fields(MarketplaceProductRecord)}


def _record_from_raw(raw: dict) -> MarketplaceProductRecord:
    """`MarketplaceCatalogStore.all_records()` returns every
    MarketplaceProductRecord field PLUS bookkeeping (`first_observed_at`/
    `last_observed_at`/`identity_ambiguous`) -- filtered here to the
    dataclass's own real fields only, dynamically (via
    dataclasses.fields()), so a future field added to either side never
    silently breaks this reconstruction."""
    return MarketplaceProductRecord(**{k: v for k, v in raw.items() if k in _RECORD_FIELD_NAMES})


def advance_marketplace_investigations(
    catalog: MarketplaceCatalogStore,
    knowledge: KnowledgeBase,
    investigations: InvestigationStore,
) -> list[Investigation]:
    """For every real, already-persisted Marketplace catalog record:
    grounds it into real OBSERVED/DERIVED Finding/Claim evidence
    (idempotent, unchanged `ground_marketplace_product()`/
    `claim_derived_economics()`), and -- only when real evidence exists
    but is still below Bridge 1's `MIN_INDEPENDENT_SOURCES` bar, and no
    Investigation already tracks this canonical subject -- opens exactly
    one real Investigation, `status="waiting_for_evidence"`. A product
    with zero real evidence yet, or one that already has enough evidence
    for Bridge 1 to act on directly, is left alone -- an Investigation
    exists only for the real, honest "interesting but not yet enough"
    gap. Returns the Investigations genuinely opened this call."""
    changed: list[Investigation] = []

    for canonical_id, raw in catalog.all_records().items():
        record = _record_from_raw(raw)
        grounded = ground_marketplace_product(record, canonical_id, knowledge)

        observed_claims = knowledge.claims(subject_id=canonical_id, predicate="observed_as")
        evidence_finding_ids = grounded.evidence_finding_ids if grounded else (
            observed_claims[0].evidence_finding_ids if observed_claims else []
        )
        if evidence_finding_ids:
            claim_derived_economics(record, canonical_id, evidence_finding_ids, knowledge)

        real_evidence_count = len(knowledge.findings(subject=canonical_id))
        if real_evidence_count == 0 or real_evidence_count >= MIN_INDEPENDENT_SOURCES:
            continue  # nothing to investigate yet, or already enough for Bridge 1 to act on

        if investigations.by_subject(MARKETPLACE_OPPORTUNITY_CATEGORY, canonical_id) is not None:
            continue  # idempotent -- already tracked, never a second Investigation

        investigation = Investigation(
            subject_id=canonical_id,
            category=MARKETPLACE_OPPORTUNITY_CATEGORY,
            status="waiting_for_evidence",
            reason_opened=(
                f"real Marketplace evidence exists ({real_evidence_count} source) but is below the "
                f"{MIN_INDEPENDENT_SOURCES}-source bar opportunity_advance.py (Bridge 1) requires"
            ),
            supporting_finding_ids=list(evidence_finding_ids),
            missing_evidence="an independent second source confirming this candidate",
        )
        investigations.save_investigation(investigation)
        changed.append(investigation)

    return changed
