from atlas.brain.kpi import KPIRegistry
from atlas.influencer.performance import STANDARD_METRICS, performance_snapshot
from atlas.influencer.registry import InfluencerRegistry


def rank_influencers(category: str, registry: InfluencerRegistry, kpis: KPIRegistry, metric_names=STANDARD_METRICS) -> list[dict]:
    """Every active influencer explicitly tagged for `category`
    (DigitalInfluencer.categories — a founder-declared structural fact,
    never inferred from free-text niche/content_style), ranked by how much
    real performance evidence exists for them.

    Deliberately not a blended numeric confidence score, unlike
    confidence.confidence_score()/provider_ranking.provider_confidence():
    raw metrics (followers, views, engagement_rate) live on incompatible
    scales, and inventing a normalization/weighting scheme before any real
    data exists to justify one would be exactly the fabricated-precision
    mistake this codebase avoids everywhere else. `factors_available` (how
    many real metrics are on record) is the honest, comparable signal
    available today — the same bootstrapping shape provider_ranking.py
    started from before any provider had a real Finding. A real weighted
    influencer_confidence() is future work, once enough real performance
    history exists to justify how metrics should be weighted against each
    other — this is the Learning & Optimization foundation to build that
    on, not the finished mechanism.
    """
    eligible = [inf for inf in registry.influencers() if inf.status == "active" and category in inf.categories]
    snapshots = [performance_snapshot(inf.id, kpis, metric_names) for inf in eligible]
    return sorted(snapshots, key=lambda s: s["factors_available"], reverse=True)


def prefer_market_match(ranked: list[dict], market: str, registry: InfluencerRegistry) -> dict | None:
    """Given rank_influencers()'s already-ranked candidates, prefers the
    highest-ranked one whose IdentityProfile.market exactly matches
    `market`, falling back to the top-ranked candidate overall when no
    candidate matches or `market` is "" (2026-08-03, Opportunity Discovery
    V1 — AffiliateOpportunity.recommended_market). Compares against
    `market` (the raw code, e.g. "US") — not `nationality` (the human name,
    e.g. "American": fixed 2026-08-03 after a live demo caught that a
    name can never equal a code, so every influencer created via the real
    Digital Influencer Factory path was silently never matching here) and
    not `language` (the language they speak). Deliberately an exact match,
    never inferred/fuzzy — the same discipline confidence.py's
    provider/subject scoping already uses. Never changes today's selection
    when no real market recommendation exists: every founder-manual
    opportunity has recommended_market == "", so this is a pure extension,
    not a behavior change, for every campaign created that way. Returns
    None only when `ranked` itself is empty (nothing to choose from)."""
    if not ranked:
        return None
    if market:
        for entry in ranked:
            influencer = registry.get_influencer(entry["influencer_id"])
            if influencer.identity.market == market:
                return entry
    return ranked[0]
