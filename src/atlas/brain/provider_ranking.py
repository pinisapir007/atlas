from atlas.brain.confidence import rank_by_confidence, recency_score, source_corroboration_score, weighted_average_of_available
from atlas.brain.knowledge import KnowledgeBase
from atlas.integrations.registry import PROVIDERS

# Provider-level confidence uses the same weighted-average-of-available-
# factors shape as confidence.confidence_score(), scoped one level deeper —
# a specific platform within a category, not the category itself. Only two
# factors are honestly computable today: source corroboration and recency,
# both from provider-tagged Findings. Historical success / measured
# outcomes / internal experiments are deliberately absent from this model —
# ATLAS doesn't yet attribute real revenue/cost per-provider (only
# per-goal), so there is no real data to build a third factor from. A
# narrower model with fewer honest inputs is correct; naming a fabricated
# third factor to make it look more complete would not be.
PROVIDER_WEIGHTS = {
    "source_corroboration": 0.6,
    "recency": 0.4,
}


def provider_confidence(category: str, provider: str, knowledge: KnowledgeBase) -> dict:
    """Evidence-weighted confidence for one specific platform within a
    category — the provider-level analog of confidence.confidence_score().
    Same fail-closed combination: a missing factor is never treated as
    zero, and zero available factors returns None, not a fabricated score.
    """
    components = {
        "source_corroboration": source_corroboration_score(category, knowledge, provider=provider),
        "recency": recency_score(category, knowledge, provider=provider),
    }
    combined = weighted_average_of_available(components, PROVIDER_WEIGHTS)

    return {
        "provider": provider,
        "category": category,
        "score": combined,
        "factors": components,
        "factors_available": sum(1 for v in components.values() if v is not None),
        "factors_total": len(components),
    }


def rank_providers(category: str, knowledge: KnowledgeBase) -> list[dict]:
    """Every registered provider eligible for `category` — found via
    CommerceProvider.category, a structural fact declared by the provider
    itself, requiring no credential or network call — ranked by
    provider_confidence() descending. Ties broken by factors_available
    (more evidence outranks a thinner score that happens to tie), the same
    discipline `atlas brain opportunities`' category ranking already uses.

    With exactly one real provider registered today, this returns a
    single-entry, trivially-ranked list — the mechanism is what's new here,
    already correct and ready the moment a second provider is registered,
    with no change needed to this function.
    """
    eligible = [name for name, provider in PROVIDERS.items() if provider.category == category]
    unranked = [provider_confidence(category, name, knowledge) for name in eligible]
    return rank_by_confidence(unranked)
