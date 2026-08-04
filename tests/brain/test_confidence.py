from datetime import datetime, timedelta, timezone

from atlas.brain.confidence import (
    confidence_score,
    historical_success_score,
    internal_experiments_score,
    measured_outcomes_score,
    rank_by_confidence,
    recency_score,
    repeatability_score,
    source_corroboration_score,
    weighted_average_of_available,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


# --- weighted_average_of_available (shared by confidence_score() and
# provider_ranking.provider_confidence() — direct coverage here since it's
# now an independently-important, shared combination rule) ------------------


def test_weighted_average_returns_none_when_nothing_available():
    assert weighted_average_of_available({"a": None, "b": None}, {"a": 0.5, "b": 0.5}) is None


def test_weighted_average_ignores_missing_factors_rather_than_treating_as_zero():
    # weight ratio 3:1 between a and c; b is missing and must not count as 0
    result = weighted_average_of_available({"a": 1.0, "b": None, "c": 0.0}, {"a": 0.3, "b": 0.5, "c": 0.1})
    assert abs(result - 0.75) < 1e-9  # (0.3*1.0 + 0.1*0.0) / (0.3+0.1)


def test_weighted_average_with_everything_available():
    result = weighted_average_of_available({"a": 1.0, "b": 0.0}, {"a": 0.5, "b": 0.5})
    assert result == 0.5


def test_rank_by_confidence_orders_by_score_descending():
    results = [{"score": 0.3, "factors_available": 2}, {"score": 0.9, "factors_available": 1}]
    ranked = rank_by_confidence(results)
    assert [r["score"] for r in ranked] == [0.9, 0.3]


def test_rank_by_confidence_ranks_none_score_lowest_without_crashing():
    results = [{"score": None, "factors_available": 0}, {"score": 0.1, "factors_available": 1}]
    ranked = rank_by_confidence(results)
    assert ranked[0]["score"] == 0.1
    assert ranked[1]["score"] is None


def test_rank_by_confidence_breaks_ties_by_factors_available():
    results = [{"score": 0.5, "factors_available": 1}, {"score": 0.5, "factors_available": 3}]
    ranked = rank_by_confidence(results)
    assert ranked[0]["factors_available"] == 3


# --- source_corroboration_score -------------------------------------------------


def test_source_corroboration_is_none_with_no_findings(tmp_path):
    assert source_corroboration_score("affiliate", _kb(tmp_path)) is None


def test_source_corroboration_ignores_findings_without_evidence(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="no source", evidence=""))

    assert source_corroboration_score("affiliate", kb) is None


def test_source_corroboration_ignores_other_categories(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="youtube", description="x", evidence="https://example.com"))

    assert source_corroboration_score("affiliate", kb) is None


def test_source_corroboration_saturates_at_three_sourced_findings(tmp_path):
    kb = _kb(tmp_path)
    for i in range(5):
        kb.save_finding(Finding(source="research", category="affiliate", description=f"f{i}", evidence=f"https://example.com/{i}"))

    assert source_corroboration_score("affiliate", kb) == 1.0


def test_source_corroboration_partial_with_two_sourced_findings(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="f1", evidence="https://example.com/1"))
    kb.save_finding(Finding(source="research", category="affiliate", description="f2", evidence="https://example.com/2"))

    assert abs(source_corroboration_score("affiliate", kb) - (2 / 3)) < 1e-9


def test_source_corroboration_scoped_to_a_provider_ignores_other_providers(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="digistore24 fact", evidence="https://x/1", provider="digistore24")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="shareasale fact", evidence="https://x/2", provider="shareasale")
    )

    assert source_corroboration_score("affiliate", kb, provider="digistore24") == 1 / 3
    assert source_corroboration_score("affiliate", kb, provider="shareasale") == 1 / 3


def test_source_corroboration_scoped_to_a_provider_ignores_category_general_findings(tmp_path):
    # A category-general finding ("affiliate marketing pays well") isn't
    # evidence FOR a specific platform — mixing it in would blur the exact
    # comparison provider-level scoping exists to make.
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="general fact", evidence="https://x/1"))

    assert source_corroboration_score("affiliate", kb, provider="digistore24") is None


def test_source_corroboration_scoped_to_a_subject_ignores_other_subjects(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA"))
    kb.save_finding(Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="BudgetWise"))

    assert source_corroboration_score("affiliate", kb, subject="KetoDNA") == 1 / 3
    assert source_corroboration_score("affiliate", kb, subject="BudgetWise") == 1 / 3


# --- recency_score -----------------------------------------------------------


def test_recency_is_none_with_no_findings(tmp_path):
    assert recency_score("affiliate", _kb(tmp_path)) is None


def test_recency_is_near_one_for_a_fresh_finding(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="fresh"))

    assert recency_score("affiliate", kb) > 0.99


def test_recency_is_near_zero_for_an_old_finding(tmp_path):
    kb = _kb(tmp_path)
    old_finding = Finding(source="research", category="affiliate", description="stale")
    old_finding.created_at = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    kb.save_finding(old_finding)

    assert recency_score("affiliate", kb) == 0.0


def test_recency_scoped_to_a_subject_ignores_other_subjects(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="a", subject="KetoDNA"))

    assert recency_score("affiliate", kb, subject="KetoDNA") > 0.99
    assert recency_score("affiliate", kb, subject="BudgetWise") is None


# --- repeatability_score -----------------------------------------------------


def test_repeatability_is_always_none(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))

    assert repeatability_score("affiliate", kb) is None


# --- historical_success_score / internal_experiments_score / measured_outcomes_score --


def test_historical_success_is_none_with_no_measured_goals(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    assert historical_success_score("affiliate", memory, kpis) is None


def test_historical_success_is_none_for_a_category_with_no_dispatchable_channel(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="youtube goal")
    memory.save_goal(goal)
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"cost_{goal.id}", 50.0)

    # "youtube" maps to no real Task category, so this must stay None even
    # though the goal itself has real profit — there's no real evidence
    # this profit came from a youtube channel specifically.
    assert historical_success_score("youtube", memory, kpis) is None


def test_historical_success_computes_win_rate_across_goals_touching_the_category(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    winner = Goal(description="profitable affiliate goal")
    memory.save_goal(winner)
    memory.save_task(Task(goal_id=winner.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{winner.id}", 100.0)
    kpis.record(f"cost_{winner.id}", 40.0)

    loser = Goal(description="unprofitable affiliate goal")
    memory.save_goal(loser)
    memory.save_task(Task(goal_id=loser.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{loser.id}", 10.0)
    kpis.record(f"cost_{loser.id}", 40.0)

    assert historical_success_score("affiliate", memory, kpis) == 0.5


def test_internal_experiments_is_none_without_engine_id(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="affiliate goal, not tagged as an experiment")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"cost_{goal.id}", 40.0)

    assert internal_experiments_score("affiliate", memory, kpis) is None


def test_internal_experiments_computes_from_engine_tagged_goals(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="Experiment 1: affiliate offer A", engine_id="affiliate_exp_1")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 100.0)
    kpis.record(f"cost_{goal.id}", 50.0)  # roi = 1.0

    assert internal_experiments_score("affiliate", memory, kpis) == 1.0


def test_measured_outcomes_is_none_without_any_roi(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    assert measured_outcomes_score("affiliate", memory, kpis) is None


def test_measured_outcomes_reflects_average_roi_magnitude(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="affiliate goal")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 200.0)
    kpis.record(f"cost_{goal.id}", 100.0)  # roi = 1.0 -> score 1.0

    assert measured_outcomes_score("affiliate", memory, kpis) == 1.0


# --- confidence_score (the combiner) ------------------------------------------


def test_confidence_score_is_none_when_no_factor_has_data(tmp_path):
    result = confidence_score("affiliate", _kb(tmp_path), _memory(tmp_path), KPIRegistry(_memory(tmp_path)))

    assert result["score"] is None
    assert result["factors_available"] == 0
    assert result["factors_total"] == 6
    assert result["factors"]["repeatability"] is None


def test_confidence_score_combines_only_available_factors(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = confidence_score("affiliate", kb, memory, kpis)

    assert result["score"] is not None
    assert result["factors_available"] == 2  # source_corroboration + recency
    assert result["factors"]["measured_outcomes"] is None
    assert result["factors"]["source_corroboration"] is not None


def test_confidence_score_rises_with_real_measured_profit(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    before = confidence_score("affiliate", kb, memory, kpis)["score"]

    goal = Goal(description="affiliate goal")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 200.0)
    kpis.record(f"cost_{goal.id}", 100.0)

    after = confidence_score("affiliate", kb, memory, kpis)["score"]

    assert after > before
