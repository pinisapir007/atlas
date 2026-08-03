from atlas.brain.kpi import KPIRegistry

# A documented, common baseline — not a fixed schema. record_metric()
# accepts any metric name, since different platforms report genuinely
# different vocabularies (TikTok's metrics aren't YouTube's); this is only
# the default set performance_snapshot() looks for when the caller doesn't
# name a more specific list.
STANDARD_METRICS = ("followers", "views", "engagement_rate")


def record_metric(influencer_id: str, metric_name: str, value: float, kpis: KPIRegistry) -> None:
    """Records a real, founder- or platform-reported performance reading
    for one influencer. A replacement reading, not accumulated — a
    follower count or engagement rate is a fact about right now, not a
    per-event amount to sum (the same replacement semantics
    _record_recruitment_result already uses for a similarly point-in-time
    fact). Reuses KPIRegistry directly rather than inventing a second
    time-series mechanism — single source of truth for named metrics."""
    kpis.record(f"{metric_name}_{influencer_id}", value)


def performance_snapshot(influencer_id: str, kpis: KPIRegistry, metric_names=STANDARD_METRICS) -> dict:
    """Real, currently-known performance for one influencer across the
    given metric names — None (never fabricated) for any metric never
    recorded. metric_names defaults to STANDARD_METRICS but accepts any
    list, since not every influencer will have the same metrics tracked
    (a YouTube-only influencer has no "duet_rate")."""
    metrics = {name: kpis.latest(f"{name}_{influencer_id}") for name in metric_names}
    return {
        "influencer_id": influencer_id,
        "metrics": metrics,
        "factors_available": sum(1 for v in metrics.values() if v is not None),
        "factors_total": len(metric_names),
    }
