"""ATLAS Opportunity Discovery Engine — multi-provider (2026-08-04).

Generalizes what was Digistore24-only discovery into a provider-agnostic
engine: any real atlas.integrations.base.MarketSignalProvider can be
supplied, and the engine keeps running if any one provider returns zero
opportunities, has no credential configured, or raises outright.
Digistore24 Marketplace becomes one optional provider among however
many are supplied — never a special case anywhere in this module. No
provider's absence or failure is fatal to any other provider's results.

Each provider is responsible for its own scoring — different providers
have fundamentally different raw data (a marketplace commission stat
and a future search-trend signal aren't measured the same way), so
there is no single formula this engine could honestly apply across all
of them. What every provider IS expected to return from fetch_signals()
is the one shared, minimal shape this engine aggregates on: a list of
dicts each shaped {"entry_id"/"id": ..., "score": float | None, "data":
{...real raw fields...}, "error": str | None}. Combining scores from
different providers into one ranked list assumes those scores are at
least roughly comparable in scale — a real, stated limitation of
cross-provider ranking, not hidden. Revisit once more than one real
provider exists to see whether that assumption actually holds.

Deliberately not wired through atlas.integrations.signal_registry.
SIGNAL_PROVIDERS: that registry stays the reserved home for a future
integrations-layer-only provider (one with no brain-side scoring of its
own). Digistore24SignalProvider's scoring is brain-layer judgment, so
it's supplied here via this engine's own `providers` parameter — the
same explicit-dependency-injection pattern every other brain module in
this codebase already uses (CEOBrain's own constructor, for one),
rather than entangling two different registration mechanisms.
"""

from atlas.brain.digistore24_opportunity_discovery import Digistore24SignalProvider
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.integrations.base import MarketSignalProvider


def _default_providers() -> list[MarketSignalProvider]:
    return [Digistore24SignalProvider()]


def discover_opportunities(
    providers: list[MarketSignalProvider] | None = None,
    knowledge: KnowledgeBase | None = None,
) -> dict:
    """Runs every supplied provider's fetch_signals(), aggregates and
    ranks every real result across all of them, and (when `knowledge` is
    given) records a real Finding per real result — the same schema
    opportunity_ranking.rank_opportunities() already consumes downstream,
    regardless of which provider produced it.

    Per-provider fault isolation is the core contract here: a provider
    that raises any exception, returns None (no credential configured),
    or returns an empty list is recorded in the returned
    "provider_status" section and simply contributes zero opportunities
    — every other provider still runs and still contributes its own
    real results. The broad `except Exception` below is deliberate: a
    provider is, from this engine's perspective, untrusted plugin code
    it doesn't control the failure modes of (mirroring this codebase's
    standing "no direct agent-to-agent calls that can cascade a failure"
    discipline, applied here to providers instead of assets) — every
    caught failure is recorded, never silently dropped.

    Returns {"opportunities": [...combined, ranked, provider-tagged
    results...], "provider_status": {provider_name: {"count": int,
    "error": str | None}, ...}} — never raises on a single provider's
    behalf.
    """
    if providers is None:
        providers = _default_providers()

    combined: list[dict] = []
    provider_status: dict[str, dict] = {}

    for provider in providers:
        try:
            signals = provider.fetch_signals()
        except Exception as exc:  # noqa: BLE001 -- deliberate: isolate one provider's failure from every other provider, see docstring
            provider_status[provider.name] = {"count": 0, "error": str(exc)}
            continue

        if signals is None:
            provider_status[provider.name] = {"count": 0, "error": "no credential configured"}
            continue

        real_results = [r for r in signals if isinstance(r, dict)]
        provider_status[provider.name] = {"count": len(real_results), "error": None}

        for result in real_results:
            tagged = dict(result)
            tagged["provider"] = provider.name
            combined.append(tagged)

            if knowledge is not None and result.get("data"):
                _save_finding(provider, result, knowledge)

    combined.sort(key=lambda r: (r.get("score") is not None, r.get("score") or 0.0), reverse=True)
    return {"opportunities": combined, "provider_status": provider_status}


def _save_finding(provider: MarketSignalProvider, result: dict, knowledge: KnowledgeBase) -> None:
    entry = result["data"]
    identifier = result.get("entry_id") or result.get("id")
    category = entry.get("product_category") or provider.category
    subject = entry.get("headline") or identifier
    if subject is None:
        return
    knowledge.save_finding(
        Finding(
            source="opportunity_discovery_engine",
            category=category,
            description=f"Real {provider.name} opportunity {identifier}: {subject}",
            provider=provider.name,
            subject=str(subject),
        )
    )
