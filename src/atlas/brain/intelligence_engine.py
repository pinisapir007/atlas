"""ATLAS Intelligence Engine V1 (2026-08-05).

The primary knowledge source for the platform. Its mission is not to
generate revenue directly — it exists to continuously improve the
quality of intelligence that enables better decisions elsewhere.
Revenue is an outcome; intelligence is the input every real decision in
this codebase (the original Decision Engine, Opportunity Discovery,
Business Execution Planning) already depends on being real and
evidence-based, never fabricated.

Collects, organizes, normalizes, and exposes intelligence across five
domains (market, human_behavior, competitor, product, economic —
atlas.integrations.base.INTELLIGENCE_DOMAINS) through one shared
interface — the same provider-based, isolated, normalized-object,
central-index architecture already proven twice in this codebase
(Resource Discovery, Multi-Source Opportunity Discovery), applied here
to a third kind of collection. This module does NOT generate
opportunities, does NOT execute any business action, and does NOT
modify any existing engine — it only collects, organizes, normalizes,
and exposes.

FindingsMarketIntelligenceProvider (market domain) is the first real
provider — see its own module for why it's real without being a new
external data source. HumanBehaviorIntelligenceProvider,
CompetitorIntelligenceProvider, ProductIntelligenceProvider, and
EconomicIntelligenceProvider are honest, structural placeholders —
always None, zero real API calls, the same "reserved, ready, not yet
built" precedent already established for the affiliate and resource
placeholder providers.

Every provider is isolated: a provider that raises, returns None (no
real source configured, or — for a placeholder — not implemented), or
returns an empty list is recorded in "provider_status" and simply
contributes zero intelligence — every other provider still runs. The
broad `except Exception` below is deliberate, the same isolation
discipline discover_opportunities()/scan_resources() already establish.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.market_intelligence_provider import FindingsMarketIntelligenceProvider
from atlas.brain.time_service import TimeService
from atlas.integrations.base import Intelligence, IntelligenceProvider
from atlas.integrations.intelligence_provider_placeholders import (
    CompetitorIntelligenceProvider,
    EconomicIntelligenceProvider,
    HumanBehaviorIntelligenceProvider,
    ProductIntelligenceProvider,
)


def _default_providers(knowledge: KnowledgeBase | None = None, time_service: TimeService | None = None) -> list[IntelligenceProvider]:
    """Every supported domain, registered by default — the market
    provider is real; the other four are honest placeholders that
    always return None until each gets its own real, credentialed
    implementation. Adding a real implementation for one of them later
    means changing exactly its own class — this list, and everything
    below it in this module, stays unchanged."""
    return [
        FindingsMarketIntelligenceProvider(knowledge, time_service),
        HumanBehaviorIntelligenceProvider(),
        CompetitorIntelligenceProvider(),
        ProductIntelligenceProvider(),
        EconomicIntelligenceProvider(),
    ]


def collect_intelligence(
    providers: list[IntelligenceProvider] | None = None,
    knowledge: KnowledgeBase | None = None,
    index: IntelligenceIndex | None = None,
    time_service: TimeService | None = None,
) -> dict:
    """Runs every supplied provider's fetch_intelligence(), aggregates
    every real result across all of them, and replaces the queryable
    IntelligenceIndex with this collection's complete, current result —
    a future consumer (Opportunity Discovery, or any other engine) can
    then read IntelligenceIndex directly without ever triggering a new
    collection itself.

    Returns {"intelligence": [...combined, real Intelligence
    objects...], "provider_status": {provider_name: {"count": int,
    "error": str | None}, ...}} — never raises on any single provider's
    behalf, and defaults to every registered provider (the real market
    provider plus the four domain placeholders) when `providers` isn't
    given.
    """
    if providers is None:
        providers = _default_providers(knowledge, time_service)
    if index is None:
        index = IntelligenceIndex()

    combined: list[Intelligence] = []
    provider_status: dict[str, dict] = {}

    for provider in providers:
        try:
            items = provider.fetch_intelligence()
        except Exception as exc:  # noqa: BLE001 -- deliberate: isolate one provider's failure from every other provider, see module docstring
            provider_status[provider.name] = {"count": 0, "error": str(exc)}
            continue

        if items is None:
            provider_status[provider.name] = {"count": 0, "error": "not available (no real data source configured, or not yet implemented)"}
            continue

        real_items = [i for i in items if isinstance(i, Intelligence)]
        provider_status[provider.name] = {"count": len(real_items), "error": None}
        combined.extend(real_items)

    index.replace_index(combined)
    return {"intelligence": combined, "provider_status": provider_status}
