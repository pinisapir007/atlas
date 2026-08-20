"""Cognitive State Wiring -- end-to-end continuity tests (2026-08-17;
updated 2026-08-17 ONE BRAIN Root Implementation).

Proves canonicalized-persistence + Finding/Claim grounding + Revisit
identity survive real process recreation, and the 12 lettered scenarios
(A-L) the founder named explicitly. The original version of this file
also proved a full Marketplace-driven Opportunity lifecycle through
`advance_marketplace_opportunity()`/`mark_candidate()`/
`plan_investigation()` -- all three were removed (see
marketplace_cognitive_bridge.py's own module docstring for why: a
second, unauthorized Opportunity writer). See
tests/brain/test_one_brain_continuity.py for the real replacement
end-to-end trace, built on the approved Investigation-based path.
"""

from pathlib import Path

from atlas.brain.inspection_memory import InspectionMemoryStore
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_cognitive_bridge import (
    claim_derived_economics,
    ground_marketplace_product,
    verify_revisit_identity,
)
from atlas.brain.marketplace_extraction import MarketplaceProductRecord, dedupe_key
from atlas.brain.models import Investigation
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.opportunity_ranking import opportunity_confidence
from atlas.integrations.traversal_completion import PageCompletionTracker

PAGE_KEY = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all?page=3"


def _record(**overrides) -> MarketplaceProductRecord:
    defaults = dict(
        product_name="Prostadine",
        category="Supplements - health",
        price=209.18,
        commission_pct=65.0,
        vendor="Prostadine",
        cart_conversion_pct=5.0,
        secondary_rate_pct=13.98,
        observed_date_raw="5/25/23",
        net_earnings_per_sale=142.73,
        earnings_per_cart_visitor=None,
        source_url="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all",
        observed_at="2026-08-17T10:00:00+00:00",
        field_notes="",
    )
    defaults.update(overrides)
    return MarketplaceProductRecord(**defaults)


# =============================================================================
# The full real, on-disk lifecycle trace: see test_one_brain_continuity.py
# =============================================================================


# =============================================================================
# A: vendor missing, then restored -> reconciles onto ONE real canonical identity
# =============================================================================


def test_scenario_a_vendor_missing_then_restored_reconciles_to_one_identity(tmp_path):
    catalog = MarketplaceCatalogStore(path=tmp_path / "catalog.json")
    full = _record(vendor="Nutraville", product_name="Unlock Earnings! Promote PinealXT!")
    _, canonical_by_raw_1 = catalog.save_records_with_identity([full])
    canonical_id = canonical_by_raw_1[dedupe_key(full)]

    partial = _record(vendor="", product_name="Unlock Earnings! Promote PinealXT!")
    _, canonical_by_raw_2 = catalog.save_records_with_identity([partial])

    assert canonical_by_raw_2[dedupe_key(partial)] == canonical_id
    assert len(catalog.known_keys()) == 1


# =============================================================================
# B: same title, different vendor -> two genuinely different real identities
# =============================================================================


def test_scenario_b_same_title_different_vendor_stays_two_identities(tmp_path):
    catalog = MarketplaceCatalogStore(path=tmp_path / "catalog.json")
    a = _record(vendor="VendorOne", product_name="Total Body Reset")
    b = _record(vendor="VendorTwo", product_name="Total Body Reset")

    _, map_a = catalog.save_records_with_identity([a])
    _, map_b = catalog.save_records_with_identity([b])

    assert map_a[dedupe_key(a)] != map_b[dedupe_key(b)]
    assert len(catalog.known_keys()) == 2


# =============================================================================
# C: same vendor, different title -> two genuinely different real identities
# =============================================================================


def test_scenario_c_same_vendor_different_title_stays_two_identities(tmp_path):
    catalog = MarketplaceCatalogStore(path=tmp_path / "catalog.json")
    a = _record(vendor="Nutraville", product_name="Product A")
    b = _record(vendor="Nutraville", product_name="Product B")

    _, map_a = catalog.save_records_with_identity([a])
    _, map_b = catalog.save_records_with_identity([b])

    assert map_a[dedupe_key(a)] != map_b[dedupe_key(b)]
    assert len(catalog.known_keys()) == 2


# =============================================================================
# D: same product across different "viewport" reads -> same identity, tracker keeps state
# =============================================================================


def test_scenario_d_same_product_across_viewports_keeps_the_same_identity(tmp_path):
    catalog = MarketplaceCatalogStore(path=tmp_path / "catalog.json")
    tracker = PageCompletionTracker()

    top_of_viewport = _record(price=209.18)
    _, map1 = catalog.save_records_with_identity([top_of_viewport])
    canonical_id = map1[dedupe_key(top_of_viewport)]
    tracker.observe(canonical_id, {"price": 209.18})
    tracker.resolve(canonical_id, "inspected")

    bottom_of_viewport = _record(price=209.18)  # the same card, now scrolled to a different screen position
    _, map2 = catalog.save_records_with_identity([bottom_of_viewport])
    assert map2[dedupe_key(bottom_of_viewport)] == canonical_id

    tracker.observe(canonical_id, {"price": 209.18})  # re-observed, same identity
    assert tracker.is_inspection_complete() is True  # inspection state untouched by re-observation


# =============================================================================
# E: same product across different runs (fresh store objects, same real file)
# =============================================================================


def test_scenario_e_same_product_across_different_runs(tmp_path):
    path = tmp_path / "catalog.json"
    run1 = MarketplaceCatalogStore(path=path)
    record = _record()
    _, map1 = run1.save_records_with_identity([record])
    canonical_id = map1[dedupe_key(record)]
    del run1

    run2 = MarketplaceCatalogStore(path=path)
    assert run2.resolve_canonical(_record()) == canonical_id


# =============================================================================
# F: same product after process recreation (covered fully in the lifecycle
# test above; this is the narrow, isolated version)
# =============================================================================


def test_scenario_f_tracker_recognizes_the_same_product_after_process_recreation(tmp_path):
    memory_path = tmp_path / "inspection_memory.json"
    original = PageCompletionTracker()
    original.observe("prostadine::prostadine", {})
    InspectionMemoryStore(path=memory_path).save_tracker(PAGE_KEY, original)
    del original

    fresh = InspectionMemoryStore(path=memory_path).load_tracker(PAGE_KEY)
    assert "prostadine::prostadine" in {r.key for r in fresh.records()}


# =============================================================================
# G: unresolved inspection survives restart
# =============================================================================


def test_scenario_g_unresolved_inspection_survives_restart(tmp_path):
    path = tmp_path / "inspection_memory.json"
    tracker = PageCompletionTracker()
    tracker.observe("a", {})
    InspectionMemoryStore(path=path).save_tracker(PAGE_KEY, tracker)

    reloaded = InspectionMemoryStore(path=path).load_tracker(PAGE_KEY)
    assert reloaded.pending_keys() == ["a"]


# =============================================================================
# H: resolved inspection stays resolved
# =============================================================================


def test_scenario_h_resolved_inspection_stays_resolved(tmp_path):
    path = tmp_path / "inspection_memory.json"
    tracker = PageCompletionTracker()
    tracker.observe("a", {})
    tracker.resolve("a", "inspected")
    InspectionMemoryStore(path=path).save_tracker(PAGE_KEY, tracker)

    reloaded = InspectionMemoryStore(path=path).load_tracker(PAGE_KEY)
    assert reloaded.is_inspection_complete() is True
    reloaded.observe("a", {"refreshed": True})  # re-observed again
    assert reloaded.is_inspection_complete() is True  # still resolved, never reset


# =============================================================================
# I: candidate reason survives restart (Investigation, not Opportunity --
# the reason-for-interest owner reassigned by the ONE BRAIN Root
# Implementation, since a candidate reason must exist BEFORE Opportunity)
# =============================================================================


def test_scenario_i_candidate_reason_survives_restart(tmp_path):
    path = tmp_path / "investigations.json"
    store = InvestigationStore(path=path)
    investigation = Investigation(
        subject_id="prostadine::prostadine", category="affiliate",
        reason_opened="high commission relative to category peers",
    )
    store.save_investigation(investigation)
    del store, investigation

    reloaded_store = InvestigationStore(path=path)
    reloaded = next(i for i in reloaded_store.investigations() if i.subject_id == "prostadine::prostadine")
    assert reloaded.reason_opened == "high commission relative to category peers"


# =============================================================================
# J: contradictory evidence survives (append-only Finding store, never overwritten)
# =============================================================================


def test_scenario_j_contradictory_evidence_survives_as_two_real_findings(tmp_path):
    path = tmp_path / "knowledge.json"
    knowledge = KnowledgeBase(path=path)
    canonical_id = "prostadine::prostadine"

    ground_marketplace_product(_record(price=209.18), canonical_id, knowledge)
    # A second, independent, contradicting real observation (e.g. a price
    # change or a differing read) is recorded directly as its own Finding
    # -- KnowledgeBase never overwrites or reconciles Findings themselves.
    from atlas.brain.models import Finding

    knowledge.save_finding(
        Finding(
            source="marketplace_catalog",
            category="affiliate",
            description="Digistore24 Marketplace listing: Prostadine, price=$189.00 (contradicts earlier reading)",
            evidence="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all",
            provider="digistore24",
            subject=canonical_id,
        )
    )

    del knowledge
    reloaded = KnowledgeBase(path=path)
    findings = reloaded.findings(subject=canonical_id)
    assert len(findings) == 2  # both real, contradicting readings preserved -- neither erased


# =============================================================================
# K: UNKNOWN survives as UNKNOWN (no fabricated derived Claim when unmeasured)
# =============================================================================


def test_scenario_k_unknown_survives_as_unknown_across_restart(tmp_path):
    path = tmp_path / "knowledge.json"
    knowledge = KnowledgeBase(path=path)
    canonical_id = "unmeasured::product"
    unmeasured = _record(cart_conversion_pct=None, net_earnings_per_sale=None, commission_pct=None)

    claim = claim_derived_economics(unmeasured, canonical_id, [], knowledge)
    assert claim is None
    del knowledge

    reloaded = KnowledgeBase(path=path)
    assert reloaded.claims(subject_id=canonical_id, predicate="economic_signal_score") == []  # still UNKNOWN


# =============================================================================
# L: no fake success probability
# =============================================================================


def test_scenario_l_no_success_probability_without_real_evidence(tmp_path):
    knowledge = KnowledgeBase(path=tmp_path / "knowledge.json")
    canonical_id = "never-observed::product"

    confidence = opportunity_confidence("affiliate", canonical_id, knowledge)
    assert confidence["score"] is None  # zero real evidence -> honestly UNKNOWN, never a fabricated number

    ground_marketplace_product(_record(), canonical_id, knowledge)
    confidence_with_evidence = opportunity_confidence("affiliate", canonical_id, knowledge)
    assert confidence_with_evidence["score"] is not None  # real evidence now produces a real number


# =============================================================================
# Selection Memory: rejection path also survives restart, symmetric to I
# =============================================================================


def test_reject_candidate_reason_also_survives_restart(tmp_path):
    path = tmp_path / "investigations.json"
    store = InvestigationStore(path=path)
    investigation = Investigation(
        subject_id="weak::product", category="affiliate", status="rejected",
        closed_reason="conversion rate too low relative to category peers",
    )
    store.save_investigation(investigation)
    del store, investigation

    reloaded_store = InvestigationStore(path=path)
    reloaded = next(i for i in reloaded_store.investigations() if i.subject_id == "weak::product")
    assert reloaded.status == "rejected"
    assert "conversion rate too low" in reloaded.closed_reason
