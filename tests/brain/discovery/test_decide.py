import pytest

from atlas.brain.discovery.decide import (
    DISCOVERY_ENGINE_ID,
    advance_executive_discovery,
    decide_all_with_discovery,
    decide_with_discovery,
)
from atlas.brain.discovery.research_request import RESEARCH_TASK_CATEGORY, research_attempts
from atlas.brain.discovery.taxonomy import BUSINESS_MODEL_CATEGORIES, MAX_RESEARCH_ATTEMPTS, MIN_CATEGORIES_EXPLORED
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding


@pytest.fixture(autouse=True)
def _executive_discovery_on(monkeypatch):
    # Off by default in real/production ticks (feature_flags.
    # executive_discovery_enabled()) -- this test module's whole purpose
    # is exercising Executive Discovery's real behavior, so every test
    # here explicitly opts in, the same convention
    # test_affiliate_intelligence_agent.py/test_decision_apply.py already
    # use for ATLAS_OPPORTUNITY_DISCOVERY_V1.
    monkeypatch.setenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", "1")


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


def _sourced(category: str, i: int) -> Finding:
    # evidence_role="direct_assertion" (2026-08-17, ONE BRAIN Evidence Role
    # Gate): scaffolding, not testing role/independence semantics itself.
    return Finding(source="research", category=category, description=f"signal {i}", evidence=f"https://example.com/{i}", evidence_role="direct_assertion")


def _explore_categories(kb, categories):
    for category in categories:
        kb.save_finding(_sourced(category, 1))
        kb.save_finding(_sourced(category, 2))


def test_decide_with_discovery_short_circuits_before_breadth_is_met(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced("digital_product", 1))
    kb.save_finding(_sourced("digital_product", 2))  # this one category alone would normally be "invest"
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide_with_discovery("digital_product", kb, memory, kpis)

    assert decision.verdict == "exploration_incomplete"
    assert decision.goal_id is None
    assert len(decision.context["explored_categories"]) < MIN_CATEGORIES_EXPLORED


def test_decide_with_discovery_defers_to_real_decide_once_breadth_is_met(tmp_path):
    kb = _kb(tmp_path)
    _explore_categories(kb, BUSINESS_MODEL_CATEGORIES[:MIN_CATEGORIES_EXPLORED])
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide_with_discovery("digital_product", kb, memory, kpis)

    assert decision.verdict == "invest"  # the real decision_engine.decide() verdict, unmodified


def test_decide_with_discovery_relabels_exhausted_insufficient_evidence(tmp_path):
    kb = _kb(tmp_path)
    _explore_categories(kb, BUSINESS_MODEL_CATEGORIES[:MIN_CATEGORIES_EXPLORED])
    kb.save_finding(_sourced("marketplace", 1))  # only one source -- stays insufficient_evidence
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for _ in range(MAX_RESEARCH_ATTEMPTS):
        kpis.record("research_attempts_marketplace", research_attempts("marketplace", kpis) + 1)

    decision = decide_with_discovery("marketplace", kb, memory, kpis)

    assert decision.verdict == "insufficient_evidence_after_research"
    assert "Research Completion Threshold" in decision.reasoning


def test_decide_all_with_discovery_covers_every_sourced_category(tmp_path):
    kb = _kb(tmp_path)
    _explore_categories(kb, BUSINESS_MODEL_CATEGORIES[:MIN_CATEGORIES_EXPLORED])
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decisions = decide_all_with_discovery(kb, memory, kpis)

    assert {d.category for d in decisions} == set(BUSINESS_MODEL_CATEGORIES[:MIN_CATEGORIES_EXPLORED])
    # "youtube" is one of the first MIN_CATEGORIES_EXPLORED taxonomy
    # categories but has no real dispatchable channel yet
    # (confidence.CATEGORY_TASK_CATEGORIES["youtube"] == set()) -- the
    # real, unmodified decide() correctly returns "propose_capability"
    # for it, never "invest". Asserting this mix (not a uniform
    # "invest") is what actually proves the wrapper passes decide()'s
    # real per-category verdict through unchanged once breadth is met,
    # rather than forcing a verdict itself.
    by_category = {d.category: d.verdict for d in decisions}
    assert by_category["youtube"] == "propose_capability"
    assert all(v == "invest" for c, v in by_category.items() if c != "youtube")


def test_advance_executive_discovery_creates_research_tasks_under_one_reused_goal(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    created = advance_executive_discovery(kb, memory, kpis)

    assert created  # every taxonomy category starts unexplored
    assert all(t.category == RESEARCH_TASK_CATEGORY for t in created)
    discovery_goals = [g for g in memory.goals() if g.engine_id == DISCOVERY_ENGINE_ID]
    assert len(discovery_goals) == 1
    assert all(t.goal_id == discovery_goals[0].id for t in created)

    # a second call reuses the same Goal rather than creating a new one
    advance_executive_discovery(kb, memory, kpis)
    assert len([g for g in memory.goals() if g.engine_id == DISCOVERY_ENGINE_ID]) == 1


def test_advance_executive_discovery_returns_nothing_once_all_research_is_exhausted(tmp_path):
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    for category in BUSINESS_MODEL_CATEGORIES:
        for _ in range(MAX_RESEARCH_ATTEMPTS):
            kpis.record(f"research_attempts_{category}", research_attempts(category, kpis) + 1)

    created = advance_executive_discovery(kb, memory, kpis)

    assert created == []


def test_decide_with_discovery_is_a_real_noop_with_the_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", raising=False)
    kb = _kb(tmp_path)
    kb.save_finding(_sourced("digital_product", 1))
    kb.save_finding(_sourced("digital_product", 2))  # only 1 explored category -- would gate if the flag were on
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide_with_discovery("digital_product", kb, memory, kpis)

    assert decision.verdict == "invest"  # exactly today's real decide() behavior, unaffected


def test_advance_executive_discovery_is_a_real_noop_with_the_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_EXECUTIVE_DISCOVERY_ENABLED", raising=False)
    kb = _kb(tmp_path)
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    created = advance_executive_discovery(kb, memory, kpis)

    assert created == []
    assert memory.goals() == []  # no Executive Discovery Goal created either
