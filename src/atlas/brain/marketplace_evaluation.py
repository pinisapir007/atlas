"""M1 Marketplace Ranking Validation (2026-08-13): evaluates and ranks
MarketplaceProductRecord evidence for further-research priority.

Deliberately reuses the codebase's one existing evidence-combination
mechanism (confidence.weighted_average_of_available() /
confidence.rank_by_confidence() -- "every confidence-based ranking in
this codebase goes through these two", per confidence.py's own docstring)
rather than inventing a new formula, per standing instruction.

Founder's explicit boundary, structurally enforced here, not just
documented: Marketplace statistics (price/commission/conversion/
earnings) are evidence inputs, never proof a product is good. Product/
vendor quality & reliability, audience/channel fit, and risk/reputation
have no real signal in Marketplace card data -- they are always reported
as unmeasured (None) here, and `verdict` stays 'requires_further_research'
whenever any of them is missing, which is every product from this data
source alone, by construction. This module never selects a product for
execution and never triggers a commercial action -- it is a read-only
research-priority ranking only.

Product vs. Offer scope note (2026-08-15, Architecture Review,
documentation-only): every score here evaluates one observed Digistore24
listing/offer's own economics (price/commission/conversion/earnings as
displayed for that specific listing) -- not a universal fact about an
underlying real-world product, and never a comparison across multiple
offers for "the same" product (no such grouping exists yet -- see
marketplace_extraction.py's module docstring). `commission_pct` alone
never determines which offer is better -- ECONOMIC_WEIGHTS deliberately
weights it lowest of the three real factors.
"""

from atlas.brain.confidence import rank_by_confidence, weighted_average_of_available
from atlas.brain.marketplace_extraction import MarketplaceProductRecord

# Stated, editable weighting (same class as confidence.WEIGHTS) -- per the
# founder's explicit instruction, commission is deliberately the smallest
# weight: a high commission % says nothing on its own about whether the
# product actually sells. Cart conversion (real buyer follow-through) and
# net earnings/sale (real per-transaction economics) carry more weight.
ECONOMIC_WEIGHTS = {
    "conversion": 0.45,
    "net_earnings": 0.35,
    "commission": 0.20,
}

# Stated, editable normalization ceilings -- same "transparent, editable
# assumption" class as affiliate_pipeline_advance.ASSUMED_MONTHLY_LEADS.
# Not derived from any real distributional data yet; revisit once enough
# real Marketplace observations exist to justify re-tuning them.
CART_CONVERSION_CEILING_PCT = 20.0
NET_EARNINGS_CEILING_USD = 100.0

# Dimensions the founder explicitly asked to be checked that Marketplace
# card data structurally cannot answer: no ratings/reviews field, no
# defined target audience/channel to compare against, no confirmed
# refund/chargeback field (secondary_rate_pct's exact meaning is
# unconfirmed -- see marketplace_extraction.MarketplaceProductRecord).
CRITICAL_UNMEASURED_DIMENSIONS = ("vendor_reliability", "audience_channel_fit", "risk_reputation")


def _normalize(value: float | None, ceiling: float) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, value / ceiling))


def economic_signal_score(record: MarketplaceProductRecord) -> dict:
    """Real Marketplace-observed economics only, combined via the shared
    fail-closed weighted_average_of_available() rule. A missing factor is
    never treated as zero; zero available factors returns score=None."""
    components = {
        "conversion": _normalize(record.cart_conversion_pct, CART_CONVERSION_CEILING_PCT),
        "net_earnings": _normalize(record.net_earnings_per_sale, NET_EARNINGS_CEILING_USD),
        "commission": _normalize(record.commission_pct, 100.0),
    }
    combined = weighted_average_of_available(components, ECONOMIC_WEIGHTS)
    return {
        "score": combined,
        "factors": components,
        "factors_available": sum(1 for v in components.values() if v is not None),
        "factors_total": len(components),
    }


def evaluate_marketplace_product(record: MarketplaceProductRecord) -> dict:
    """One product's research-stage evaluation: a real economic signal
    plus an honest accounting of the dimensions Marketplace card data
    cannot answer. `verdict` is 'requires_further_research' whenever any
    critical dimension is unmeasured -- true for every product evaluated
    from this data source alone, by design: the founder's instruction was
    to say so explicitly rather than force a choice on insufficient
    evidence. This function makes no promotion recommendation and takes
    no action."""
    economic = economic_signal_score(record)
    quality_dimensions = {dimension: None for dimension in CRITICAL_UNMEASURED_DIMENSIONS}
    missing = [d for d in CRITICAL_UNMEASURED_DIMENSIONS if quality_dimensions[d] is None]
    verdict = "requires_further_research" if missing else "sufficient_evidence"

    return {
        "product_name": record.product_name,
        "category": record.category,
        "vendor": record.vendor,
        "source_url": record.source_url,
        "observed_at": record.observed_at,
        "economic_signal": economic,
        "score": economic["score"],
        "factors_available": economic["factors_available"],
        "factors_total": economic["factors_total"],
        "quality_dimensions": quality_dimensions,
        "missing_critical_dimensions": missing,
        "verdict": verdict,
        "raw_evidence": {
            "price": record.price,
            "commission_pct": record.commission_pct,
            "cart_conversion_pct": record.cart_conversion_pct,
            "secondary_rate_pct": record.secondary_rate_pct,
            "net_earnings_per_sale": record.net_earnings_per_sale,
            "earnings_per_cart_visitor": record.earnings_per_cart_visitor,
            "observed_date_raw": record.observed_date_raw,
        },
        "field_notes": record.field_notes,
    }


def rank_marketplace_products(records: list[MarketplaceProductRecord]) -> list[dict]:
    """Ranks by real economic signal via the shared
    confidence.rank_by_confidence() tie-break rule -- not a new sort. This
    ranks *further-research priority*, never a promotion decision: every
    entry's own 'verdict' stays 'requires_further_research' until real
    quality/fit/risk evidence exists."""
    evaluated = [evaluate_marketplace_product(r) for r in records]
    return rank_by_confidence(evaluated)
