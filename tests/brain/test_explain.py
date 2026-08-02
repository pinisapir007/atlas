from atlas.brain.explain import explain_opportunity
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


def test_explanation_includes_evidence_used(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="real signal", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["evidence"] == "https://example.com"


def test_probability_of_success_is_none_with_no_track_record(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert result["probability_of_success"] is None


def test_probability_of_success_is_the_real_historical_win_rate(tmp_path):
    kb = _kb(tmp_path)
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

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert result["probability_of_success"] == 0.5


def test_expected_roi_is_none_when_nothing_measured(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert result["expected_roi"] is None


def test_expected_roi_reflects_real_measured_roi(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="affiliate goal")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 200.0)
    kpis.record(f"cost_{goal.id}", 100.0)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert result["expected_roi"] == 1.0


def test_risks_flag_no_dispatchable_channel_for_youtube_and_ugc(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="youtube", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("youtube", kb, memory, kpis)

    assert any("no dispatchable execution channel" in r for r in result["risks"])


def test_risks_flag_placeholder_channel_for_digital_product(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="digital_product", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("digital_product", kb, memory, kpis)

    assert any("hardcoded placeholder" in r for r in result["risks"])


def test_risks_flag_placeholder_channel_for_content(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="content", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("content", kb, memory, kpis)

    assert any("hardcoded placeholder" in r for r in result["risks"])


def test_risks_do_not_flag_placeholder_for_affiliate_real_chain(tmp_path):
    # affiliate's bootstrap target is affiliate_pipeline (the real
    # affiliate_department chain), not revenue_affiliate (which is itself
    # a placeholder) — must not be flagged just because a placeholder
    # exists somewhere in the broader category's task-category family.
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert not any("hardcoded placeholder" in r for r in result["risks"])


def test_risks_do_not_flag_placeholder_for_recruitment_real_channel(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="recruitment", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("recruitment", kb, memory, kpis)

    assert not any("hardcoded placeholder" in r for r in result["risks"])


def test_risks_flag_no_measured_outcomes_when_none_exist(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert any("no real measured revenue/cost" in r for r in result["risks"])


def test_risks_flag_negative_roi(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    goal = Goal(description="affiliate goal")
    memory.save_goal(goal)
    memory.save_task(Task(goal_id=goal.id, description="x", category="affiliate_pipeline"))
    kpis.record(f"revenue_{goal.id}", 10.0)
    kpis.record(f"cost_{goal.id}", 100.0)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert any("negative" in r for r in result["risks"])


def test_missing_evidence_lists_every_unavailable_factor(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert "repeatability across markets" in result["missing_evidence"]
    assert "measured outcomes" in result["missing_evidence"]


def test_rank_reason_includes_rank_number_when_given(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis, rank=1)

    assert result["rank_reason"].startswith("ranked #1")


def test_rank_reason_names_available_factors(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x", evidence="https://example.com"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert "number/quality of independent sources" in result["rank_reason"]


def test_explanation_for_a_category_with_no_findings_reflects_no_evidence(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    result = explain_opportunity("affiliate", kb, memory, kpis)

    assert result["evidence"] == []
    assert result["confidence"]["score"] is None
    assert result["rank_reason"] == "no evidence recorded yet for this category"
