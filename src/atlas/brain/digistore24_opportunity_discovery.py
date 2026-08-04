"""ATLAS Opportunity Discovery Engine for Digistore24 (2026-08-04,
Mission #001) — turns real Digistore24 marketplace data into real,
ranked opportunities and real Finding records the existing Decision
Engine pipeline (opportunity_ranking.py) already knows how to consume.
No new ranking mechanism is invented here — this module's only job is
producing real Finding records; opportunity_ranking.rank_opportunities()
does the actual ranking, unchanged.

Built and verified against this account's real, live-confirmed state: a
real call to listMarketplaceEntries returned result=success, count=0,
entries=[]. Digistore24's own OpenAPI spec describes this endpoint as
scoped "for a vendor," and this account is affiliate-only with no
products of its own — an empty result here is the correct, expected
outcome, not a failure. This module runs the identical code path
whether zero entries or real entries come back, so it is already
correct for the moment this account (or a future one) has real ones,
without a special-cased empty branch that could silently diverge from
the real one.

Every field this module scores on (product_category, affiliate_share,
stats_conversion_rate, stats_cancel_rate, stats_count_affiliates_with_sales,
stats_affiliate_profit_visitor, stats_affiliate_profit_sale) comes from
Digistore24's own official OpenAPI spec for getMarketplaceEntry — real,
sourced field names, not invented ones. None has been observed in a
real, live getMarketplaceEntry response yet (this account has had no
real entry_id to test one with), so scoring is deliberately None-safe:
a missing field is never treated as zero, the same discipline
confidence.weighted_average_of_available() already applies elsewhere in
this codebase.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.integrations.base import Opportunity
from atlas.integrations.digistore24 import Digistore24APIError, Digistore24Provider

# Digistore24's own already-computed real per-sale/per-visitor affiliate
# profit stats — preferred over recombining raw conversion/commission
# ourselves, since Digistore24 has already done that real computation.
_PROFIT_FIELDS = ("stats_affiliate_profit_sale", "stats_affiliate_profit_visitor")

# Stated, editable dampening/weighting (the same class of transparent
# assumption as confidence.HASHTAG_PLATFORMS or affiliate_pipeline_advance.
# ASSUMED_MONTHLY_LEADS) -- not a claim of optimality. Revisit once real
# scored outcomes exist to tune against.
_COMPETITION_DAMPENING_DIVISOR = 10.0


def _extract_entries(raw_list_response: dict | None) -> list[dict]:
    """Digistore24's real envelope shape for listMarketplaceEntries has
    not been fully, unambiguously confirmed — the one real response seen
    so far (result=success, count=0, entries=[]) doesn't disambiguate a
    flat vs. data-nested shape at zero entries. Checks both plausible
    real shapes rather than assuming one; never invents entries that
    aren't actually there either way."""
    if not isinstance(raw_list_response, dict):
        return []
    if isinstance(raw_list_response.get("entries"), list):
        return raw_list_response["entries"]
    data = raw_list_response.get("data")
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    if isinstance(data, list):
        return data
    return []


def _extract_entry_id(entry: dict) -> str | None:
    entry_id = entry.get("id") if isinstance(entry, dict) else None
    if entry_id is None and isinstance(entry, dict):
        entry_id = entry.get("entry_id")
    return str(entry_id) if entry_id is not None else None


def _unwrap_single_entry(raw_response: dict | None) -> dict:
    if not isinstance(raw_response, dict):
        return {}
    data = raw_response.get("data")
    return data if isinstance(data, dict) else raw_response


def score_marketplace_entry(entry: dict) -> float | None:
    """Real revenue-potential score for one real, enriched marketplace
    entry (a getMarketplaceEntry response, already unwrapped to its real
    fields) — None-safe: only combines fields actually present as real
    numbers, never a fabricated default. None when zero usable fields
    are present, never a fabricated 0.0 — the same "unmeasured is not
    zero" discipline confidence_score() already applies.

    Primary signal: Digistore24's own real, already-computed per-sale/
    per-visitor affiliate profit stats. Modulated down by real
    competition (stats_count_affiliates_with_sales — more affiliates
    already selling it lowers the score) and real risk
    (stats_cancel_rate) when those specific fields are present; neither
    is required for a score to exist.
    """
    if not isinstance(entry, dict):
        return None

    profit_values = [entry.get(f) for f in _PROFIT_FIELDS]
    profit_values = [v for v in profit_values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not profit_values:
        return None
    score = sum(profit_values) / len(profit_values)

    competition = entry.get("stats_count_affiliates_with_sales")
    if isinstance(competition, (int, float)) and not isinstance(competition, bool) and competition > 0:
        score = score / (1 + competition / _COMPETITION_DAMPENING_DIVISOR)

    cancel_rate = entry.get("stats_cancel_rate")
    if isinstance(cancel_rate, (int, float)) and not isinstance(cancel_rate, bool):
        score = score * max(0.0, 1 - cancel_rate)

    return score


def fetch_digistore24_opportunity_signals(provider: Digistore24Provider) -> list[dict] | None:
    """The real, provider-only discovery step (2026-08-04, extracted so
    both the standalone Digistore24 CLI command and the multi-provider
    Opportunity Discovery Engine — opportunity_discovery_engine.py — call
    exactly one implementation): list real candidate marketplace entries
    -> enrich each with real getMarketplaceEntry data -> score with real
    fields only. No Finding-saving here — that's a provider-agnostic
    concern the caller handles the same way for every provider, not
    duplicated per provider.

    None means no credential configured — the same MarketSignalProvider.
    fetch_signals() contract Digistore24SignalProvider (below) exposes
    this through: "never an empty list standing in for 'checked, found
    nothing' when nothing was actually checked." A real, confirmed-live
    empty marketplace (this account's actual state — listMarketplaceEntries
    returning zero entries, Digistore24's own documented vendor-only
    scoping correctly applying to an affiliate-only account) returns []
    — a real check that found nothing, genuinely different from not
    being able to check at all.

    A getMarketplaceEntry call that fails for one specific entry (e.g. a
    genuine permission error on that one product) is recorded in that
    entry's own result and skipped, not fatal to the whole run — every
    other real candidate still gets scored.
    """
    raw_list = provider.list_marketplace_entries()
    if raw_list is None:
        return None  # no credential configured -- could not check at all

    entries = _extract_entries(raw_list)
    results: list[dict] = []

    for summary_entry in entries:
        entry_id = _extract_entry_id(summary_entry)
        if entry_id is None:
            continue

        try:
            raw_entry_response = provider.get_marketplace_entry(entry_id)
        except Digistore24APIError as exc:
            results.append({"entry_id": entry_id, "score": None, "data": {}, "error": str(exc)})
            continue

        enriched = _unwrap_single_entry(raw_entry_response)
        score = score_marketplace_entry(enriched)
        results.append({"entry_id": entry_id, "score": score, "data": enriched, "error": None})

    results.sort(key=lambda r: (r["score"] is not None, r["score"] or 0.0), reverse=True)
    return results


def discover_and_rank_digistore24_opportunities(
    provider: Digistore24Provider, knowledge: KnowledgeBase | None = None
) -> list[dict]:
    """Digistore24-only discovery + real Finding-saving — unchanged
    behavior/signature from when this was the only provider; now a thin
    wrapper around fetch_digistore24_opportunity_signals() so the single-
    provider CLI command (`atlas affiliate digistore24
    discover-opportunities`) keeps working exactly as before. For
    multi-provider discovery, see opportunity_discovery_engine.py, which
    calls fetch_digistore24_opportunity_signals() directly (via
    Digistore24SignalProvider below) and does the same Finding-saving
    generically for every provider, not just this one.

    Unlike fetch_digistore24_opportunity_signals(), this function keeps
    its original, always-a-list contract (never None) for backward
    compatibility with its existing callers/tests — "no credential
    configured" and "checked, found nothing" both normalize to [] here,
    at this boundary, rather than being distinguished the way the
    MarketSignalProvider-facing function below needs to.
    """
    results = fetch_digistore24_opportunity_signals(provider)
    if results is None:
        results = []
    if knowledge is not None:
        for result in results:
            if result["data"]:
                _save_finding_for_result(provider.name, provider.category, result, knowledge)
    return results


def _save_finding_for_result(provider_name: str, provider_category: str, result: dict, knowledge: KnowledgeBase) -> None:
    entry = result["data"]
    category = entry.get("product_category") or provider_category
    subject = entry.get("headline") or result["entry_id"]
    knowledge.save_finding(
        Finding(
            source="digistore24_opportunity_discovery",
            category=category,
            description=f"Real Digistore24 marketplace entry {result['entry_id']}: {subject}",
            provider=provider_name,
            subject=str(subject),
        )
    )


class Digistore24SignalProvider:
    """Adapts fetch_digistore24_opportunity_signals() into both
    atlas.integrations.base.MarketSignalProvider (fetch_signals(), the
    original, broader-scoped Protocol) and OpportunityProvider
    (fetch_opportunities(), the newer, opportunity-specific one used by
    the multi-provider Opportunity Discovery Engine) — lives in
    atlas.brain (not atlas.integrations) because scoring
    (score_marketplace_entry()) is brain-layer business judgment, the
    same layering atlas.brain.provider_ranking already builds directly
    on atlas.integrations primitives without atlas.integrations ever
    importing back from atlas.brain. Registered with the multi-provider
    Opportunity Discovery Engine so Digistore24 is called exactly like
    any other provider — no Digistore24-special-cased path there."""

    name = "digistore24"
    category = "affiliate"

    def __init__(self, provider: Digistore24Provider | None = None):
        self._provider = provider if provider is not None else Digistore24Provider()

    def fetch_signals(self) -> list[dict] | None:
        return fetch_digistore24_opportunity_signals(self._provider)

    def fetch_opportunities(self) -> list[Opportunity] | None:
        """Satisfies OpportunityProvider — converts this provider's raw,
        already-scored discovery results into normalized Opportunity
        objects. None propagates exactly as fetch_signals() already
        does (no credential configured); a per-entry enrichment failure
        becomes a real Opportunity with `error` set and `score=None`
        rather than being dropped, so the engine can still report it."""
        raw_results = fetch_digistore24_opportunity_signals(self._provider)
        if raw_results is None:
            return None
        return [
            Opportunity(
                provider=self.name,
                external_id=r["entry_id"],
                title=(r["data"].get("headline") or r["entry_id"]) if r["data"] else r["entry_id"],
                category=(r["data"].get("product_category") or self.category) if r["data"] else self.category,
                score=r["score"],
                raw=r["data"],
                error=r["error"],
            )
            for r in raw_results
        ]
