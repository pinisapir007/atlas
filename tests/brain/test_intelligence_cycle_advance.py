from atlas.brain.intelligence_cycle_advance import advance_intelligence_cycle
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal


def _world(tmp_path):
    memory = BrainMemory(tmp_path / "brain.json")
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    kpis = KPIRegistry(memory)
    return memory, knowledge, kpis


def test_runs_the_real_workflow_for_an_active_intelligence_sourced_goal_with_sufficient_evidence(tmp_path):
    memory, knowledge, kpis = _world(tmp_path)
    knowledge.save_finding(Finding(source="a", category="affiliate", description="signal one", evidence="https://a.example", evidence_role="direct_assertion"))
    knowledge.save_finding(Finding(source="b", category="affiliate", description="signal two", evidence="https://b.example", evidence_role="direct_assertion"))
    goal = Goal(description="Pursue affiliate opportunities", engine_id="intelligence_affiliate")
    memory.save_goal(goal)

    results = advance_intelligence_cycle(memory, knowledge, kpis)

    assert len(results) == 1
    assert results[0].category == "affiliate"
    assert results[0].goal == "Pursue affiliate opportunities"
    assert results[0].status == "completed"
    assert results[0].halted is False


def test_halts_before_the_decision_engine_when_evidence_is_insufficient_but_still_returns_a_real_result(tmp_path):
    memory, knowledge, kpis = _world(tmp_path)
    goal = Goal(description="Pursue affiliate opportunities", engine_id="intelligence_affiliate")
    memory.save_goal(goal)

    results = advance_intelligence_cycle(memory, knowledge, kpis)

    assert len(results) == 1
    assert results[0].status == "halted_before_decision_engine"
    assert results[0].halted is True


def test_skips_a_goal_with_no_engine_id(tmp_path):
    memory, knowledge, kpis = _world(tmp_path)
    memory.save_goal(Goal(description="Founder-created goal, no engine_id"))

    assert advance_intelligence_cycle(memory, knowledge, kpis) == []


def test_skips_a_goal_whose_engine_id_is_not_an_intelligence_category(tmp_path):
    memory, knowledge, kpis = _world(tmp_path)
    memory.save_goal(Goal(description="Some other engine's goal", engine_id="recruitment_lead_42"))

    assert advance_intelligence_cycle(memory, knowledge, kpis) == []


def test_skips_a_paused_or_done_intelligence_sourced_goal(tmp_path):
    memory, knowledge, kpis = _world(tmp_path)
    memory.save_goal(Goal(description="paused", engine_id="intelligence_affiliate", status="paused"))
    memory.save_goal(Goal(description="done", engine_id="intelligence_affiliate", status="done"))

    assert advance_intelligence_cycle(memory, knowledge, kpis) == []


def test_runs_once_per_eligible_goal_when_multiple_categories_are_active(tmp_path):
    memory, knowledge, kpis = _world(tmp_path)
    for category in ("affiliate", "digital_product"):
        memory.save_goal(Goal(description=f"Pursue {category} opportunities", engine_id=f"intelligence_{category}"))

    results = advance_intelligence_cycle(memory, knowledge, kpis)

    assert {r.category for r in results} == {"affiliate", "digital_product"}
