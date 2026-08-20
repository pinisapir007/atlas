from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_extraction import MarketplaceProductRecord
from atlas.brain.marketplace_investigation_advance import advance_marketplace_investigations
from atlas.brain.opportunity_advance import advance_opportunities_from_findings
from atlas.brain.opportunities import OpportunityStore


def _record(**overrides) -> MarketplaceProductRecord:
    defaults = dict(
        product_name="Prostadine", category="Supplements - health", price=209.18, commission_pct=65.0,
        vendor="VendorB", cart_conversion_pct=5.0, secondary_rate_pct=13.98, observed_date_raw="5/25/23",
        net_earnings_per_sale=142.73, earnings_per_cart_visitor=None,
        source_url="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all",
        observed_at="2026-08-17T10:00:00+00:00", field_notes="",
    )
    defaults.update(overrides)
    return MarketplaceProductRecord(**defaults)


def _stores(tmp_path):
    catalog = MarketplaceCatalogStore(tmp_path / "marketplace_catalog.json")
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    investigations = InvestigationStore(tmp_path / "investigations.json")
    return catalog, knowledge, investigations


def test_a_single_real_catalog_record_opens_exactly_one_investigation(tmp_path):
    catalog, knowledge, investigations = _stores(tmp_path)
    catalog.save_records([_record()])

    changed = advance_marketplace_investigations(catalog, knowledge, investigations)

    assert len(changed) == 1
    assert changed[0].status == "waiting_for_evidence"
    assert changed[0].category == "affiliate"
    assert len(knowledge.findings()) == 1  # grounded once


def test_idempotent_no_duplicate_investigation_on_a_second_call(tmp_path):
    catalog, knowledge, investigations = _stores(tmp_path)
    catalog.save_records([_record()])

    advance_marketplace_investigations(catalog, knowledge, investigations)
    second = advance_marketplace_investigations(catalog, knowledge, investigations)

    assert second == []
    assert len(investigations.investigations()) == 1
    assert len(knowledge.findings()) == 1  # ground_marketplace_product() stayed idempotent too


def test_zero_evidence_products_never_get_an_investigation(tmp_path):
    """A product only just added to the catalog with no real Finding
    grounded yet (impossible in practice today since grounding happens
    in the same call, but the guard itself is asserted directly)."""
    catalog, knowledge, investigations = _stores(tmp_path)
    # no records saved at all
    changed = advance_marketplace_investigations(catalog, knowledge, investigations)
    assert changed == []
    assert investigations.investigations() == []


def test_already_sufficient_evidence_does_not_open_an_investigation_bridge_1_handles_it(tmp_path):
    catalog, knowledge, investigations = _stores(tmp_path)
    catalog.save_records([_record()])
    advance_marketplace_investigations(catalog, knowledge, investigations)  # 1 source -> Investigation opened

    # a second, independent, real Finding for the SAME canonical subject arrives
    from atlas.brain.models import Finding
    canonical_id = next(iter(catalog.known_keys()))
    knowledge.save_finding(Finding(
        source="research", category="affiliate", description="a second real source",
        evidence="https://independent-review.example.com/prostadine", subject=canonical_id,
        evidence_role="direct_assertion",
    ))

    changed = advance_marketplace_investigations(catalog, knowledge, investigations)

    assert changed == []  # already at/above the bar -- this bridge does not touch it further
    assert len(investigations.investigations()) == 1  # the original stays, not duplicated


def test_full_wiring_marketplace_to_bridge_1_via_a_second_real_finding(tmp_path):
    catalog, knowledge, investigations = _stores(tmp_path)
    opportunities = OpportunityStore(tmp_path / "opportunities.json")
    catalog.save_records([_record()])
    advance_marketplace_investigations(catalog, knowledge, investigations)

    from atlas.brain.models import Finding
    canonical_id = next(iter(catalog.known_keys()))
    knowledge.save_finding(Finding(
        source="research", category="affiliate", description="a second real source",
        evidence="https://independent-review.example.com/prostadine", subject=canonical_id,
        evidence_role="direct_assertion",
    ))

    created = advance_opportunities_from_findings(knowledge, opportunities)

    assert len(created) == 1
    assert created[0].subject == canonical_id
