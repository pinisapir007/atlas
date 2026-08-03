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
