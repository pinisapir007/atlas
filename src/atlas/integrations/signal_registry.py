from atlas.integrations.base import MarketSignalProvider

# Empty by design (2026-08-03, Opportunity Discovery V1) — no real
# market-signal source is integrated yet; adding one means picking a
# specific real, credentialed data source, the same kind of separate,
# explicit decision atlas.integrations.registry.PROVIDERS started from
# before Digistore24 was integrated. Discovery honestly finds nothing until
# a real provider is registered here — never a fabricated placeholder (see
# atlas.brain.opportunity_ranking.rank_opportunities()).
SIGNAL_PROVIDERS: dict[str, MarketSignalProvider] = {}


def get_signal_providers(category: str) -> list[MarketSignalProvider]:
    """Every registered MarketSignalProvider eligible for `category` —
    found via MarketSignalProvider.category, a structural fact declared by
    the provider itself, the same no-credential-required lookup
    provider_ranking.rank_providers() already uses for CommerceProvider."""
    return [provider for provider in SIGNAL_PROVIDERS.values() if provider.category == category]
