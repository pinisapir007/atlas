"""Reserved, honest placeholder IntelligenceProviders (2026-08-05,
ATLAS Intelligence Engine V1) — Human Behavior, Competitor, Product, and
Economic Intelligence.

Each satisfies atlas.integrations.base.IntelligenceProvider structurally
(name/domain/fetch_intelligence()) so the Intelligence Engine can
register and run them exactly like the real market-intelligence
provider — but none has a real API/research call anywhere in it. This
mirrors the exact "reserved, zero implementations" precedent already
established for affiliate_provider_placeholders.py and
resource_provider_placeholders.py: picking and building a real,
credentialed source for any one of these (a real consumer-research
panel, a real competitor-tracking service, a real product-review
aggregator, a real economic-data feed) is a separate, explicit decision
for each — not something registering the class name here implies is
ready. fetch_intelligence() always returns None (never a fabricated
insight, never a fake empty-but-successful check) until a real
implementation replaces it.

HumanBehaviorIntelligenceProvider carries one additional, non-negotiable
boundary, restated from this domain's own founding directive: this
exists ONLY to understand people, never to manipulate them or optimize
deception. That boundary applies to whatever real implementation
eventually replaces this placeholder too — a future implementation
returning real Intelligence objects must stay purely observational
(a real, cited pain point or motivation), never a "trigger" or
"exploit" framing.
"""

from atlas.integrations.base import Intelligence


class HumanBehaviorIntelligenceProvider:
    """Placeholder for real human behavior research (decision-making,
    motivations, pain points, desires, buying behavior, customer
    journey, behavioral patterns). No real data source exists —
    understanding people is this domain's only mission; manipulating
    them or optimizing deception is never in scope, for this placeholder
    or any real implementation that replaces it."""

    name = "human_behavior_intelligence"
    domain = "human_behavior"

    def fetch_intelligence(self) -> list[Intelligence] | None:
        return None


class CompetitorIntelligenceProvider:
    """Placeholder for real competitor intelligence (competitors,
    products, positioning, pricing, strengths, weaknesses). No real data
    source exists yet — a real competitor-tracking integration is a
    separate, explicit decision, not made here."""

    name = "competitor_intelligence"
    domain = "competitor"

    def fetch_intelligence(self) -> list[Intelligence] | None:
        return None


class ProductIntelligenceProvider:
    """Placeholder for real product intelligence (quality, value,
    features, differentiation). No real data source exists yet."""

    name = "product_intelligence"
    domain = "product"

    def fetch_intelligence(self) -> list[Intelligence] | None:
        return None


class EconomicIntelligenceProvider:
    """Placeholder for real economic intelligence (markets, countries,
    economic trends, purchasing power, seasonal effects). No real data
    source exists yet."""

    name = "economic_intelligence"
    domain = "economic"

    def fetch_intelligence(self) -> list[Intelligence] | None:
        return None
