from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, StrategicObjective
from atlas.brain.scoring import blended_score, score_cash_flow, score_strategic_value


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def test_cash_flow_score_ranks_higher_revenue_goal_higher(tmp_path):
    kpis = _kpis(tmp_path)
    strong = Goal(description="strong", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak", founder_estimate={"expected_revenue": 100.0})
    cohort = [strong, weak]

    assert score_cash_flow(strong, cohort, kpis) > score_cash_flow(weak, cohort, kpis)


def test_cash_flow_score_favors_lower_investment_and_faster_profit(tmp_path):
    kpis = _kpis(tmp_path)
    cheap_fast = Goal(
        description="cheap and fast",
        founder_estimate={"required_investment": 50.0, "time_to_first_profit": 7.0},
    )
    costly_slow = Goal(
        description="costly and slow",
        founder_estimate={"required_investment": 5000.0, "time_to_first_profit": 180.0},
    )
    cohort = [cheap_fast, costly_slow]

    assert score_cash_flow(cheap_fast, cohort, kpis) > score_cash_flow(costly_slow, cohort, kpis)


def test_strategic_value_independent_of_cash_flow(tmp_path):
    kpis = _kpis(tmp_path)
    long_bet = Goal(
        description="long-term asset",
        founder_estimate={
            "expected_revenue": 0.0,
            "scalability": 0.9,
            "automation_potential": 0.9,
            "long_term_strategic_value": 0.9,
        },
    )
    quick_cash = Goal(
        description="quick cash",
        founder_estimate={
            "expected_revenue": 1000.0,
            "scalability": 0.1,
            "automation_potential": 0.1,
            "long_term_strategic_value": 0.1,
        },
    )
    cohort = [long_bet, quick_cash]

    assert score_strategic_value(long_bet, cohort, kpis) > score_strategic_value(quick_cash, cohort, kpis)
    assert score_cash_flow(quick_cash, cohort, kpis) > score_cash_flow(long_bet, cohort, kpis)


def test_horizons_scored_separately(tmp_path):
    kpis = _kpis(tmp_path)
    short_a = Goal(description="short a", horizon="short", founder_estimate={"expected_revenue": 100.0})
    short_b = Goal(description="short b", horizon="short", founder_estimate={"expected_revenue": 200.0})
    long_extreme = Goal(
        description="long extreme", horizon="long", founder_estimate={"expected_revenue": 1_000_000.0}
    )
    all_goals = [short_a, short_b, long_extreme]

    score_before = score_cash_flow(short_a, [short_a, short_b], kpis)
    score_with_long_present = score_cash_flow(short_a, all_goals, kpis)

    assert score_before == score_with_long_present


def test_single_goal_cohort_is_neutral(tmp_path):
    kpis = _kpis(tmp_path)
    goal = Goal(description="only active goal", founder_estimate={"expected_revenue": 5000.0})

    assert score_cash_flow(goal, [goal], kpis) == 0.5
    assert score_strategic_value(goal, [goal], kpis) == 0.5


def test_score_reflects_measured_kpi_over_stale_founder_estimate(tmp_path):
    from atlas.brain.valuation import MATURITY_SAMPLE

    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    optimistic_but_flat = Goal(description="optimistic", founder_estimate={"expected_revenue": 900.0})
    modest_but_growing = Goal(description="modest", founder_estimate={"expected_revenue": 100.0})
    for _ in range(MATURITY_SAMPLE):
        kpis.record(f"revenue_{modest_but_growing.id}", 5000.0)

    cohort = [optimistic_but_flat, modest_but_growing]

    assert score_cash_flow(modest_but_growing, cohort, kpis) > score_cash_flow(optimistic_but_flat, cohort, kpis)


def test_blended_score_with_no_objective_reproduces_the_legacy_per_horizon_rule(tmp_path):
    kpis = _kpis(tmp_path)
    short_goal = Goal(
        description="short",
        horizon="short",
        founder_estimate={"expected_revenue": 1000.0, "scalability": 0.1},
    )
    cohort = [short_goal]

    assert blended_score(short_goal, cohort, kpis, objective=None) == score_cash_flow(short_goal, cohort, kpis)

    long_goal = Goal(
        description="long",
        horizon="long",
        founder_estimate={"expected_revenue": 1000.0, "scalability": 0.1},
    )
    cohort_long = [long_goal]
    assert blended_score(long_goal, cohort_long, kpis, objective=None) == score_strategic_value(long_goal, cohort_long, kpis)


def test_blended_score_with_a_real_objective_blends_both_scores_by_its_real_weights(tmp_path):
    kpis = _kpis(tmp_path)
    cash_heavy = Goal(
        description="cash heavy",
        horizon="short",
        founder_estimate={"expected_revenue": 1000.0, "scalability": 0.0, "automation_potential": 0.0, "long_term_strategic_value": 0.0},
    )
    strategic_heavy = Goal(
        description="strategic heavy",
        horizon="short",
        founder_estimate={"expected_revenue": 0.0, "scalability": 1.0, "automation_potential": 1.0, "long_term_strategic_value": 1.0},
    )
    cohort = [cash_heavy, strategic_heavy]

    cash_first_objective = StrategicObjective(
        description="first $1,000", target_metric="revenue", target_value=1000.0,
        cash_flow_weight=1.0, strategic_value_weight=0.0,
    )
    assert blended_score(cash_heavy, cohort, kpis, cash_first_objective) > blended_score(strategic_heavy, cohort, kpis, cash_first_objective)

    scale_objective = StrategicObjective(
        description="sustainable scale", target_metric="revenue", target_value=10000.0,
        cash_flow_weight=0.0, strategic_value_weight=1.0,
    )
    assert blended_score(strategic_heavy, cohort, kpis, scale_objective) > blended_score(cash_heavy, cohort, kpis, scale_objective)
