from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.influencer.performance import performance_snapshot, record_metric


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def test_record_metric_is_a_replacement_reading_not_accumulated(tmp_path):
    kpis = _kpis(tmp_path)

    record_metric("influencer-a", "followers", 1000.0, kpis)
    record_metric("influencer-a", "followers", 1200.0, kpis)

    assert kpis.latest("followers_influencer-a") == 1200.0  # the current true count, not a sum


def test_record_metric_accepts_any_metric_name(tmp_path):
    kpis = _kpis(tmp_path)

    record_metric("influencer-a", "duet_rate", 0.42, kpis)

    assert kpis.latest("duet_rate_influencer-a") == 0.42


def test_performance_snapshot_is_none_for_unmeasured_metrics(tmp_path):
    kpis = _kpis(tmp_path)

    snapshot = performance_snapshot("influencer-a", kpis)

    assert snapshot["metrics"] == {"followers": None, "views": None, "engagement_rate": None}
    assert snapshot["factors_available"] == 0
    assert snapshot["factors_total"] == 3


def test_performance_snapshot_reflects_recorded_metrics(tmp_path):
    kpis = _kpis(tmp_path)
    record_metric("influencer-a", "followers", 5000.0, kpis)
    record_metric("influencer-a", "engagement_rate", 0.08, kpis)

    snapshot = performance_snapshot("influencer-a", kpis)

    assert snapshot["metrics"]["followers"] == 5000.0
    assert snapshot["metrics"]["engagement_rate"] == 0.08
    assert snapshot["metrics"]["views"] is None
    assert snapshot["factors_available"] == 2


def test_performance_snapshot_accepts_a_custom_metric_list(tmp_path):
    kpis = _kpis(tmp_path)
    record_metric("influencer-a", "subscribers", 300.0, kpis)

    snapshot = performance_snapshot("influencer-a", kpis, metric_names=("subscribers", "watch_time"))

    assert snapshot["metrics"] == {"subscribers": 300.0, "watch_time": None}
    assert snapshot["factors_total"] == 2


def test_metrics_never_cross_contaminate_between_influencers(tmp_path):
    kpis = _kpis(tmp_path)
    record_metric("influencer-a", "followers", 1000.0, kpis)
    record_metric("influencer-b", "followers", 50.0, kpis)

    assert performance_snapshot("influencer-a", kpis)["metrics"]["followers"] == 1000.0
    assert performance_snapshot("influencer-b", kpis)["metrics"]["followers"] == 50.0
