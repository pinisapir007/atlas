from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal
from atlas.brain.valuation import (
    MATURITY_SAMPLE,
    blended,
    kpi_reading_count,
    maturity,
    measured_value,
)


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def test_maturity_zero_with_no_kpi_data(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    assert kpi_reading_count(goal, kpis) == 0
    assert maturity(goal, kpis) == 0.0


def test_maturity_saturates_at_one(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    for value in range(MATURITY_SAMPLE):
        kpis.record(f"revenue_{goal.id}", float(value))
    assert maturity(goal, kpis) == 1.0


def test_maturity_partial(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 10.0)
    kpis.record(f"cost_{goal.id}", 5.0)
    assert maturity(goal, kpis) == 2 / MATURITY_SAMPLE


def test_measured_value_expected_revenue_uses_latest_kpi(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"revenue_{goal.id}", 250.0)
    assert measured_value(goal, kpis, "expected_revenue") == 250.0


def test_measured_value_required_investment_uses_latest_kpi(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    kpis.record(f"cost_{goal.id}", 40.0)
    assert measured_value(goal, kpis, "required_investment") == 40.0


def test_measured_value_none_for_judgment_only_criteria(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow")
    for criterion in ("scalability", "automation_potential", "long_term_strategic_value"):
        assert measured_value(goal, kpis, criterion) is None


def test_measured_time_to_first_profit_detects_crossover(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    goal = Goal(description="grow", created_at="2026-01-01T00:00:00+00:00")

    memory.record_kpi(f"cost_{goal.id}", 100.0, "2026-01-02T00:00:00+00:00")
    memory.record_kpi(f"revenue_{goal.id}", 50.0, "2026-01-03T00:00:00+00:00")  # still behind cost
    memory.record_kpi(f"revenue_{goal.id}", 150.0, "2026-01-06T00:00:00+00:00")  # now ahead

    assert measured_value(goal, kpis, "time_to_first_profit") == 5.0


def test_measured_time_to_first_profit_none_when_never_profitable(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    goal = Goal(description="grow", created_at="2026-01-01T00:00:00+00:00")

    memory.record_kpi(f"cost_{goal.id}", 100.0, "2026-01-02T00:00:00+00:00")
    memory.record_kpi(f"revenue_{goal.id}", 50.0, "2026-01-03T00:00:00+00:00")

    assert measured_value(goal, kpis, "time_to_first_profit") is None


def test_blended_uses_founder_estimate_when_no_kpi_data(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow", founder_estimate={"expected_revenue": 500.0})
    assert blended(goal, kpis, "expected_revenue") == 500.0


def test_blended_fully_measured_at_full_maturity(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow", founder_estimate={"expected_revenue": 500.0})
    for _ in range(MATURITY_SAMPLE):
        kpis.record(f"revenue_{goal.id}", 900.0)
    assert blended(goal, kpis, "expected_revenue") == 900.0


def test_blended_partial_weight_at_partial_maturity(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow", founder_estimate={"expected_revenue": 400.0})
    half = MATURITY_SAMPLE // 2
    for _ in range(half):
        kpis.record(f"revenue_{goal.id}", 800.0)

    weight = half / MATURITY_SAMPLE
    expected = (1 - weight) * 400.0 + weight * 800.0
    assert blended(goal, kpis, "expected_revenue") == expected


def test_blended_returns_none_with_no_founder_estimate_and_no_measurement(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="unscored")
    assert blended(goal, kpis, "required_investment") is None
    assert blended(goal, kpis, "time_to_first_profit") is None
    assert blended(goal, kpis, "scalability") is None


def test_blended_falls_through_to_founder_estimate_for_judgment_only_criteria(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="grow", founder_estimate={"scalability": 0.7})
    for _ in range(MATURITY_SAMPLE):
        kpis.record(f"revenue_{goal.id}", 900.0)  # high maturity, irrelevant to scalability
    assert blended(goal, kpis, "scalability") == 0.7
