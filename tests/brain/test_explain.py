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
