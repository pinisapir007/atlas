from datetime import datetime, timedelta, timezone

from atlas.brain.confidence import (
    confidence_score,
    historical_success_score,
    internal_experiments_score,
    measured_outcomes_score,
    recency_score,
    repeatability_score,
    source_corroboration_score,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


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
