import pytest

from atlas.brain.deep_research_advance import advance_deep_research, categories_needing_deep_research
from atlas.brain.discovery.deep_research_request import DEEP_RESEARCH_TASK_CATEGORY, category_from_deep_research_task
from atlas.brain.discovery.research_request import research_attempts
from atlas.brain.discovery.taxonomy import MAX_RESEARCH_ATTEMPTS
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


@pytest.fixture(autouse=True)
def _enable_executive_discovery(monkeypatch):
    # This whole bridge inherits Executive Discovery's own Dev/Production
    # flag -- explicitly enabled here so these tests exercise the real
    # behavior, the same pattern discovery/test_decide.py already uses.
    monkeypatch.setenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", "1")


def test_noop_when_executive_discovery_flag_is_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", raising=False)
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)

    assert advance_deep_research(memory, kb, kpis) == []


def test_categories_needing_deep_research_requires_shallow_exhaustion(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    # Not yet exhausted at the shallow level -- deep research must not
    # claim it yet; the shallow Research Trigger still owns it.
    assert "saas" not in categories_needing_deep_research(kb, kpis)

    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)

    assert "saas" in categories_needing_deep_research(kb, kpis)


def test_advance_deep_research_creates_one_reversible_task_per_exhausted_category(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)

    created = advance_deep_research(memory, kb, kpis)

    assert len(created) == 1
    [task] = created
    assert task.category == DEEP_RESEARCH_TASK_CATEGORY
    assert task.reversible is True
    assert category_from_deep_research_task(task) == "saas"


def test_advance_deep_research_does_not_duplicate_an_open_task(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)
    advance_deep_research(memory, kb, kpis)

    second_round = advance_deep_research(memory, kb, kpis)

    assert second_round == []


def test_advance_deep_research_retries_once_the_open_task_resolves(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)
    [first] = advance_deep_research(memory, kb, kpis)
    first.status = "failed"
    memory.save_task(first)

    second_round = advance_deep_research(memory, kb, kpis)

    assert len(second_round) == 1


def test_advance_deep_research_shares_the_standing_executive_discovery_goal(tmp_path):
    from atlas.brain.discovery.decide import DISCOVERY_ENGINE_ID

    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_saas", research_attempts("saas", kpis) + 1)

    [task] = advance_deep_research(memory, kb, kpis)

    goal = next(g for g in memory.goals() if g.id == task.goal_id)
    assert goal.engine_id == DISCOVERY_ENGINE_ID
