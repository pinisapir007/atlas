"""ATLAS Multi-Source Opportunity Discovery Engine V1 (2026-08-04).

Discovers revenue opportunities from multiple real (or honestly
placeholder) affiliate sources through one shared interface. Digistore24
is the first real provider; Amazon Associates, AliExpress Affiliate, CJ,
Impact, and ShareASale are registered as honest, structural placeholders
(atlas.integrations.affiliate_provider_placeholders) — each satisfies
the same OpportunityProvider Protocol so the engine's core never changes
when a placeholder is later replaced with a real implementation, and
never changes to add a seventh provider beyond that either. The engine
keeps running if any one provider returns zero opportunities, has no
credential configured, raises outright, or (for a placeholder) simply
isn't built yet — no provider's absence or failure is fatal to any
other provider's real results.

Every provider normalizes its own real data into the shared
atlas.integrations.base.Opportunity shape before this engine ever sees
it — this engine does not know or care that a Digistore24 marketplace
entry's real fields look nothing like a future Amazon Associates
result's real fields. Combining scores from different providers into
one ranked list assumes those scores are at least roughly comparable in
scale — a real, stated limitation of cross-provider ranking, not
hidden. Revisit once more than one real (non-placeholder) provider
exists to see whether that assumption actually holds.

Merge -> deduplicate -> rank (2026-08-05): every real result from every
provider is aggregated, then _deduplicate() collapses exact
(provider, external_id) repeats before ranking or Finding-saving — see
discover_opportunities()'s own docstring for why cross-provider
similarity matching (e.g. by title) is deliberately not attempted.

Deliberately not wired through atlas.integrations.signal_registry.
SIGNAL_PROVIDERS: that registry stays the reserved home for a future
MarketSignalProvider (a broader concept — search trends, social
trending topics — not necessarily a scored "opportunity"). Every
provider here is supplied via this engine's own `providers` parameter —
the same explicit-dependency-injection pattern every other brain module
in this codebase already uses (CEOBrain's own constructor, for one),
rather than entangling two different registration mechanisms.
"""

from atlas.brain.digistore24_opportunity_discovery import Digistore24SignalProvider
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.integrations.affiliate_provider_placeholders import (
    AliExpressAffiliateProvider,
    AmazonAssociatesProvider,
    CJProvider,
    ImpactProvider,
    ShareASaleProvider,
)
from atlas.integrations.base import Opportunity, OpportunityProvider


def _default_providers() -> list[OpportunityProvider]:
    """Every supported source, registered by default — Digistore24 is
    real; the other five are honest placeholders that always return
    None until each gets its own real, credentialed implementation.
    Adding a real implementation for one of them later means changing
    exactly its own class in affiliate_provider_placeholders.py — this
    list, and everything below it in this module, stays unchanged."""
    return [
        Digistore24SignalProvider(),
        AmazonAssociatesProvider(),
        AliExpressAffiliateProvider(),
        CJProvider(),
        ImpactProvider(),
        ShareASaleProvider(),
    ]


def discover_opportunities(
    providers: list[OpportunityProvider] | None = None,
    knowledge: KnowledgeBase | None = None,
) -> dict:
    """Runs every supplied provider's fetch_opportunities(), aggregates
    and ranks every real result across all of them, and (when
    `knowledge` is given) records a real Finding per real, error-free
    result — the same schema opportunity_ranking.rank_opportunities()
    already consumes downstream, regardless of which provider produced
    it.

    Per-provider fault isolation is the core contract here: a provider
    that raises any exception, returns None (no credential configured,
    or — for a placeholder — not implemented at all), or returns an
    empty list is recorded in the returned "provider_status" section and
    simply contributes zero opportunities — every other provider still
    runs and still contributes its own real results. The broad `except
    Exception` below is deliberate: a provider is, from this engine's
    perspective, untrusted plugin code it doesn't control the failure
    modes of (mirroring this codebase's standing "no direct agent-to-
    agent calls that can cascade a failure" discipline, applied here to
    providers instead of assets) — every caught failure is recorded,
    never silently dropped.

    Merge -> deduplicate -> rank, in that order: every provider's real
    results are aggregated first (isolated per-provider, see above),
    then _deduplicate() collapses exact (provider, external_id) repeats
    before anything is ranked or saved as a Finding — so a provider bug
    or an accidentally-duplicated entry in `providers` can never inflate
    the ranked list or double-record the same real opportunity.
    `provider_status["count"]` still reports each provider's own raw
    count, before dedup — an honest record of what that specific
    provider actually returned, independent of what the merge step did
    with it afterward.

    Returns {"opportunities": [...merged, deduplicated, ranked
    Opportunity objects...], "provider_status": {provider_name:
    {"count": int, "error": str | None}, ...}} — never raises on any
    single provider's behalf, and defaults to every registered provider
    (Digistore24 plus the five placeholders) when `providers` isn't
    given.
    """
    if providers is None:
        providers = _default_providers()

    combined: list[Opportunity] = []
    provider_status: dict[str, dict] = {}

    for provider in providers:
        try:
            opportunities = provider.fetch_opportunities()
        except Exception as exc:  # noqa: BLE001 -- deliberate: isolate one provider's failure from every other provider, see docstring
            provider_status[provider.name] = {"count": 0, "error": str(exc)}
            continue

        if opportunities is None:
            provider_status[provider.name] = {"count": 0, "error": "not available (no credential configured, or not yet implemented)"}
            continue

        real_opportunities = [o for o in opportunities if isinstance(o, Opportunity)]
        provider_status[provider.name] = {"count": len(real_opportunities), "error": None}
        combined.extend(real_opportunities)

    deduplicated = _deduplicate(combined)

    for opportunity in deduplicated:
        if knowledge is not None and opportunity.raw and not opportunity.error:
            _save_finding(opportunity, knowledge)

    deduplicated.sort(key=lambda o: (o.score is not None, o.score or 0.0), reverse=True)
    return {"opportunities": deduplicated, "provider_status": provider_status}


def _deduplicate(opportunities: list[Opportunity]) -> list[Opportunity]:
    """Merges duplicates on the one honest, unambiguous identity signal
    available: an exact match on (provider, external_id). Deliberately
    never dedupes across providers by title/category similarity — two
    different real affiliate networks share no common product-identity
    standard, and fuzzy-matching them would risk silently conflating two
    genuinely distinct real opportunities into one, exactly the kind of
    fabricated-precision mistake this codebase's fail-closed rule exists
    to prevent. Protects against a provider bug, or the same provider
    appearing twice in a caller-supplied `providers` list, double-
    counting the same real opportunity — first occurrence wins,
    deterministic ordering."""
    seen: set[tuple[str, str]] = set()
    deduplicated: list[Opportunity] = []
    for opportunity in opportunities:
        key = (opportunity.provider, opportunity.external_id)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(opportunity)
    return deduplicated


def _save_finding(opportunity: Opportunity, knowledge: KnowledgeBase) -> None:
    knowledge.save_finding(
        Finding(
            source="opportunity_discovery_engine",
            category=opportunity.category or opportunity.provider,
            description=f"Real {opportunity.provider} opportunity {opportunity.external_id}: {opportunity.title}",
            provider=opportunity.provider,
            subject=opportunity.title,
        )
    )
