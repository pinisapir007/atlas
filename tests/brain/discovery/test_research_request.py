import pytest

from atlas.brain.discovery.research_request import (
    RESEARCH_TASK_CATEGORY,
    categories_needing_research,
    category_from_research_task,
    create_research_tasks,
    research_attempts,
    research_exhausted,
    research_task_description,
)
from atlas.brain.discovery.taxonomy import MAX_RESEARCH_ATTEMPTS
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Task


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


def test_research_task_description_round_trips():
    task = Task(goal_id="g1", description=research_task_description("saas"))
    assert category_from_research_task(task) == "saas"


def test_category_from_research_task_rejects_a_non_research_task():
    task = Task(goal_id="g1", description="some other task")
    with pytest.raises(ValueError, match="not a real research-trigger task"):
        category_from_research_task(task)


def test_categories_needing_research_includes_unexplored_categories(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    needing = categories_needing_research(kb, kpis)

    assert "saas" in needing


def test_categories_needing_research_excludes_exhausted_categories(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)

    assert research_exhausted("saas", kpis) is True
    assert "saas" not in categories_needing_research(kb, kpis)


def test_create_research_tasks_creates_one_reversible_task_per_category(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    created = create_research_tasks("goal-1", ["saas", "marketplace"], memory, kpis)

    assert len(created) == 2
    assert {t.category for t in created} == {RESEARCH_TASK_CATEGORY}
    assert all(t.reversible for t in created)
    assert research_attempts("saas", kpis) == 1
    assert research_attempts("marketplace", kpis) == 1


def test_create_research_tasks_does_not_duplicate_an_open_task(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    create_research_tasks("goal-1", ["saas"], memory, kpis)

    second_round = create_research_tasks("goal-1", ["saas"], memory, kpis)

    assert second_round == []
    assert research_attempts("saas", kpis) == 1  # not incremented again


def test_create_research_tasks_retries_once_the_open_task_is_resolved(tmp_path):
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    [first] = create_research_tasks("goal-1", ["saas"], memory, kpis)
    first.status = "failed"
    memory.save_task(first)

    second_round = create_research_tasks("goal-1", ["saas"], memory, kpis)

    assert len(second_round) == 1
    assert research_attempts("saas", kpis) == 2
