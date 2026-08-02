from atlas.brain.intelligence_advance import advance_intelligence
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


def _sourced_finding(category: str, i: int) -> Finding:
    return Finding(source="research", category=category, description=f"signal {i}", evidence=f"https://example.com/{i}")


def test_does_not_promote_with_only_one_source(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    goals, tasks = advance_intelligence(kb, memory, kpis)

    assert goals == []
    assert tasks == []


def test_promotes_a_channel_ready_category_with_two_independent_sources(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    goals, tasks = advance_intelligence(kb, memory, kpis)

    assert len(goals) == 1
    assert goals[0].engine_id == "intelligence_digital_product"
    assert goals[0].founder_estimate == {}  # no fabricated founder judgment
    assert len(tasks) == 1
    assert tasks[0].category == "revenue_digital_product"
    assert tasks[0].goal_id == goals[0].id
    assert tasks[0].reversible is True


def test_findings_without_evidence_never_count_toward_the_source_minimum(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(Finding(source="research", category="digital_product", description="no source", evidence=""))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    goals, tasks = advance_intelligence(kb, memory, kpis)

    assert goals == []


def test_does_not_repromote_a_category_already_promoted(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    first_goals, first_tasks = advance_intelligence(kb, memory, kpis)
    for g in first_goals:
        memory.save_goal(g)
    for t in first_tasks:
        memory.save_task(t)

    second_goals, second_tasks = advance_intelligence(kb, memory, kpis)

    assert second_goals == []
    assert second_tasks == []


def test_does_not_promote_a_channel_a_real_goal_already_pursues(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))
    kb.save_finding(_sourced_finding("affiliate", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    existing = Goal(description="a human already created this affiliate goal")
    memory.save_goal(existing)
    memory.save_task(Task(goal_id=existing.id, description="x", category="affiliate_pipeline"))

    goals, tasks = advance_intelligence(kb, memory, kpis)

    assert goals == []
    assert tasks == []


def test_channel_less_category_produces_a_capability_gap_task_not_a_real_channel(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("youtube", 1))
    kb.save_finding(_sourced_finding("youtube", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    goals, tasks = advance_intelligence(kb, memory, kpis)

    assert len(goals) == 1
    assert "Capability gap" in goals[0].description
    assert tasks[0].category == "create_asset"
    assert tasks[0].reversible is False  # default — create_asset always requires approval regardless


def test_channel_less_capability_gap_is_not_repeated_every_call(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("youtube", 1))
    kb.save_finding(_sourced_finding("youtube", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    first_goals, first_tasks = advance_intelligence(kb, memory, kpis)
    for g in first_goals:
        memory.save_goal(g)

    second_goals, second_tasks = advance_intelligence(kb, memory, kpis)

    assert second_goals == []
    assert second_tasks == []


def test_promotes_multiple_independent_categories_in_one_call(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    kb.save_finding(_sourced_finding("recruitment", 1))
    kb.save_finding(_sourced_finding("recruitment", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    goals, tasks = advance_intelligence(kb, memory, kpis)

    assert {g.engine_id for g in goals} == {"intelligence_digital_product", "intelligence_recruitment"}
