from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_cognitive_bridge import (
    claim_derived_economics,
    ground_marketplace_product,
    verify_revisit_identity,
)
from atlas.brain.marketplace_extraction import MarketplaceProductRecord


def _knowledge() -> KnowledgeBase:
    return KnowledgeBase(store=_FakeStore())


def _catalog() -> MarketplaceCatalogStore:
    return MarketplaceCatalogStore(store=_FakeStore())


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


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


CANONICAL = "prostadine::prostadine"


# --- OBSERVED FACT: ground_marketplace_product() ----------------------------


def test_ground_marketplace_product_creates_a_real_finding_and_observation_claim():
    knowledge = _knowledge()
    claim = ground_marketplace_product(_record(), CANONICAL, knowledge)

    assert claim is not None
    assert claim.subject_id == CANONICAL
    assert claim.claim_type == "observation"
    assert claim.source == "manual"
    assert claim.object_value == "Prostadine"
    finding = knowledge.get_finding(claim.evidence_finding_ids[0])
    assert finding.subject == CANONICAL
    assert finding.evidence == _record().source_url


def test_ground_marketplace_product_marketplace_invariant_claimant_unknown_role_aggregated():
    """ONE BRAIN Evidence Role Gate (2026-08-17) -- locked invariant: this
    Finding is genuinely MIXED (vendor-set fields + platform-computed
    stats, two real, different possible claimants) -- claimant MUST stay
    "" (never "improved" to digistore24/vendor), and evidence_role MUST
    stay "aggregated_report" (safe to trust via origin alone, capped at
    exactly one independent-source group by Finding-level granularity)."""
    knowledge = _knowledge()
    claim = ground_marketplace_product(_record(), CANONICAL, knowledge)
    finding = knowledge.get_finding(claim.evidence_finding_ids[0])

    assert finding.claimant == ""
    assert finding.evidence_role == "aggregated_report"


def test_ground_marketplace_product_is_idempotent():
    knowledge = _knowledge()
    ground_marketplace_product(_record(), CANONICAL, knowledge)
    second = ground_marketplace_product(_record(), CANONICAL, knowledge)

    assert second is None
    assert len(knowledge.claims(subject_id=CANONICAL, predicate="observed_as")) == 1


# --- DERIVED FACT: claim_derived_economics() --------------------------------


def test_claim_derived_economics_creates_an_inference_claim_from_the_real_formula():
    knowledge = _knowledge()
    grounded = ground_marketplace_product(_record(), CANONICAL, knowledge)
    claim = claim_derived_economics(_record(), CANONICAL, grounded.evidence_finding_ids, knowledge)

    assert claim is not None
    assert claim.claim_type == "inference"
    assert claim.predicate == "economic_signal_score"
    assert float(claim.object_value) >= 0.0


def test_claim_derived_economics_returns_none_when_score_is_none():
    knowledge = _knowledge()
    unmeasured = _record(cart_conversion_pct=None, net_earnings_per_sale=None, commission_pct=None)
    claim = claim_derived_economics(unmeasured, CANONICAL, [], knowledge)
    assert claim is None


def test_claim_derived_economics_is_idempotent():
    knowledge = _knowledge()
    claim_derived_economics(_record(), CANONICAL, [], knowledge)
    second = claim_derived_economics(_record(), CANONICAL, [], knowledge)
    assert second is None


# --- Revisit Contract ---------------------------------------------------------


def test_verify_revisit_identity_true_for_the_same_real_product():
    catalog = _catalog()
    catalog.save_records([_record()])
    assert verify_revisit_identity(CANONICAL, _record(), catalog) is True


def test_verify_revisit_identity_true_even_when_vendor_is_transiently_missing():
    """The revisit contract must survive the exact real anomaly the Audit
    found -- a transient vendor-missing partial-render read for the SAME
    real product must still resolve to the expected canonical identity."""
    catalog = _catalog()
    catalog.save_records([_record()])  # real vendor recorded first
    partial = _record(vendor="")
    assert verify_revisit_identity(CANONICAL, partial, catalog) is True


def test_verify_revisit_identity_fails_closed_for_a_different_product():
    catalog = _catalog()
    catalog.save_records([_record()])
    different = _record(product_name="Glucotonic", vendor="skyhighperformers")
    assert verify_revisit_identity(CANONICAL, different, catalog) is False


# --- R: repeated observation from the same real-world origin counts once ---


def test_r_repeated_observation_of_the_same_product_never_creates_a_second_finding():
    """ground_marketplace_product()'s existing idempotency (checked via
    a real Claim lookup, not a new mechanism) already guarantees this:
    the same product re-observed any number of times contributes at
    most ONE real Finding toward Bridge 1's MIN_INDEPENDENT_SOURCES
    count -- repeated observation of one real-world origin is never
    mistaken for multiple independent sources."""
    knowledge = _knowledge()
    ground_marketplace_product(_record(), CANONICAL, knowledge)
    ground_marketplace_product(_record(price=215.00), CANONICAL, knowledge)  # re-observed, refreshed price
    ground_marketplace_product(_record(price=220.00), CANONICAL, knowledge)  # re-observed again

    assert len(knowledge.findings(subject=CANONICAL)) == 1


# --- Removed-writer regression guard (2026-08-17, ONE BRAIN Root Implementation) ---


def test_module_no_longer_exposes_any_opportunity_writer():
    """Structural regression guard: the three removed functions
    (advance_marketplace_opportunity/mark_candidate/reject_candidate)
    must never quietly reappear -- Bridge 1 (opportunity_advance.py)
    remains the ONLY creator of atlas.brain.models.Opportunity."""
    import atlas.brain.marketplace_cognitive_bridge as mod

    assert not hasattr(mod, "advance_marketplace_opportunity")
    assert not hasattr(mod, "mark_candidate")
    assert not hasattr(mod, "reject_candidate")
    assert not hasattr(mod, "plan_investigation")
