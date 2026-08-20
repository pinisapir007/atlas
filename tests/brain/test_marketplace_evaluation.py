from atlas.brain.marketplace_evaluation import (
    CRITICAL_UNMEASURED_DIMENSIONS,
    economic_signal_score,
    evaluate_marketplace_product,
    rank_marketplace_products,
)
from atlas.brain.marketplace_extraction import MarketplaceProductRecord


def _record(**overrides) -> MarketplaceProductRecord:
    defaults = dict(
        product_name="Test Product",
        category="Downloads",
        price=50.0,
        commission_pct=75.0,
        vendor="testvendor",
        cart_conversion_pct=10.0,
        secondary_rate_pct=5.0,
        observed_date_raw="1/1/26",
        net_earnings_per_sale=40.0,
        earnings_per_cart_visitor=None,
        source_url="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all",
        observed_at="2026-08-13T12:00:00+00:00",
        field_notes="",
    )
    defaults.update(overrides)
    return MarketplaceProductRecord(**defaults)


def test_economic_signal_score_combines_all_three_real_factors_when_present():
    result = economic_signal_score(_record(cart_conversion_pct=10.0, net_earnings_per_sale=40.0, commission_pct=75.0))

    assert result["factors_available"] == 3
    assert result["factors_total"] == 3
    assert result["score"] is not None
    assert 0.0 <= result["score"] <= 1.0


def test_economic_signal_score_never_treats_a_missing_factor_as_zero():
    with_all = economic_signal_score(_record(cart_conversion_pct=10.0, net_earnings_per_sale=40.0, commission_pct=75.0))
    missing_commission = economic_signal_score(_record(cart_conversion_pct=10.0, net_earnings_per_sale=40.0, commission_pct=None))

    assert missing_commission["factors_available"] == 2
    # reweighted average of the remaining two factors, not silently zeroed
    assert missing_commission["score"] is not None
    assert missing_commission["score"] != with_all["score"] * (2 / 3)


def test_economic_signal_score_returns_none_when_every_factor_is_missing():
    result = economic_signal_score(_record(cart_conversion_pct=None, net_earnings_per_sale=None, commission_pct=None))

    assert result["score"] is None
    assert result["factors_available"] == 0


def test_commission_alone_never_dominates_the_ranking():
    """The founder's explicit instruction: never rank by highest commission
    alone. A product with a much higher commission % but weak real
    conversion/earnings must not outrank a product with strong real
    conversion/earnings and a modest commission."""
    high_commission_weak_economics = economic_signal_score(
        _record(commission_pct=95.0, cart_conversion_pct=1.0, net_earnings_per_sale=5.0)
    )
    modest_commission_strong_economics = economic_signal_score(
        _record(commission_pct=40.0, cart_conversion_pct=18.0, net_earnings_per_sale=90.0)
    )

    assert modest_commission_strong_economics["score"] > high_commission_weak_economics["score"]


def test_evaluate_marketplace_product_always_names_the_unmeasured_critical_dimensions():
    result = evaluate_marketplace_product(_record())

    assert result["missing_critical_dimensions"] == list(CRITICAL_UNMEASURED_DIMENSIONS)
    for dimension in CRITICAL_UNMEASURED_DIMENSIONS:
        assert result["quality_dimensions"][dimension] is None


def test_evaluate_marketplace_product_verdict_is_requires_further_research_even_with_strong_economics():
    """A product with excellent real economic evidence still must not be
    treated as 'proven good' -- vendor reliability, audience fit, and
    risk/reputation have no signal in Marketplace card data, so the
    verdict must stay honest regardless of how strong the economic score
    is."""
    result = evaluate_marketplace_product(_record(commission_pct=100.0, cart_conversion_pct=20.0, net_earnings_per_sale=100.0))

    assert result["score"] == 1.0
    assert result["verdict"] == "requires_further_research"


def test_evaluate_marketplace_product_never_takes_or_implies_an_action():
    result = evaluate_marketplace_product(_record())

    assert "promote" not in str(result).lower()
    assert "link" not in {k.lower() for k in result}


def test_rank_marketplace_products_orders_by_real_economic_score_descending():
    weak = _record(product_name="Weak", commission_pct=10.0, cart_conversion_pct=1.0, net_earnings_per_sale=2.0)
    strong = _record(product_name="Strong", commission_pct=80.0, cart_conversion_pct=18.0, net_earnings_per_sale=95.0)

    ranked = rank_marketplace_products([weak, strong])

    assert [r["product_name"] for r in ranked] == ["Strong", "Weak"]


def test_rank_marketplace_products_every_entry_still_requires_further_research():
    records = [
        _record(product_name="A", commission_pct=80.0, cart_conversion_pct=18.0, net_earnings_per_sale=95.0),
        _record(product_name="B", commission_pct=10.0, cart_conversion_pct=1.0, net_earnings_per_sale=2.0),
    ]

    ranked = rank_marketplace_products(records)

    assert all(r["verdict"] == "requires_further_research" for r in ranked)


def test_rank_marketplace_products_with_no_records_returns_empty_list():
    assert rank_marketplace_products([]) == []
