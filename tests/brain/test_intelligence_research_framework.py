import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from atlas.brain.intelligence_research_framework import (
    DEFAULT_RESEARCH_PRIORITY,
    ResearchFramework,
    build_research_framework,
)
from atlas.brain.time_service import TimeService
from atlas.integrations.base import INTELLIGENCE_DOMAINS

_GOAL = "Become the world's best Affiliate Marketing business"
_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_objective_echoes_the_real_verbatim_goal():
    framework = build_research_framework(_GOAL)
    assert framework.objective == _GOAL


def test_raises_on_an_empty_goal():
    with pytest.raises(ValueError, match="non-empty business goal"):
        build_research_framework("")


def test_raises_on_a_whitespace_only_goal():
    with pytest.raises(ValueError, match="non-empty business goal"):
        build_research_framework("   ")


def test_every_required_section_is_present():
    framework = build_research_framework(_GOAL)
    assert isinstance(framework, ResearchFramework)
    assert framework.objective
    assert framework.success_definition
    assert framework.current_world_leaders_question
    assert framework.knowledge_gaps
    assert framework.research_questions
    assert framework.intelligence_categories
    assert framework.required_intelligence_sources
    assert framework.missing_knowledge
    assert framework.research_priority
    assert framework.completion_criteria
    assert framework.created_at


def test_is_deterministic_given_the_same_real_goal():
    ts = TimeService(clock=lambda: _NOW)
    first = build_research_framework(_GOAL, ts)
    second = build_research_framework(_GOAL, ts)
    assert first == second


def test_two_different_goals_produce_different_objectives():
    a = build_research_framework("Goal A")
    b = build_research_framework("Goal B")
    assert a.objective != b.objective
    assert a.research_questions != b.research_questions


def test_intelligence_categories_reuses_the_real_intelligence_engine_domains():
    framework = build_research_framework(_GOAL)
    assert set(framework.intelligence_categories) == INTELLIGENCE_DOMAINS


def test_one_real_research_question_per_domain_containing_the_real_goal_text():
    framework = build_research_framework(_GOAL)
    domains_covered = {q.domain for q in framework.research_questions}
    assert domains_covered == INTELLIGENCE_DOMAINS
    for q in framework.research_questions:
        assert _GOAL in q.question


def test_human_behavior_question_states_the_understanding_only_boundary():
    framework = build_research_framework(_GOAL)
    human_behavior_question = next(q for q in framework.research_questions if q.domain == "human_behavior")
    assert "never for manipulation" in human_behavior_question.question.lower() or "understanding only" in human_behavior_question.question.lower()


def test_required_intelligence_sources_matches_the_real_registered_providers():
    framework = build_research_framework(_GOAL)
    by_domain = {s.domain: s.provider_name for s in framework.required_intelligence_sources}
    assert by_domain == {
        "market": "findings_market_intelligence",
        "human_behavior": "human_behavior_intelligence",
        "competitor": "competitor_intelligence",
        "product": "product_intelligence",
        "economic": "economic_intelligence",
    }


def test_current_world_leaders_is_a_question_never_a_fabricated_name():
    framework = build_research_framework(_GOAL)
    text = framework.current_world_leaders_question
    assert _GOAL in text
    assert "unknown" in text.lower()
    assert "no automated real-world identification exists" in text


def test_completion_criteria_honestly_reports_zero_answered_at_creation():
    framework = build_research_framework(_GOAL)
    n = len(framework.research_questions)
    assert f"0 of {n} answered" in framework.completion_criteria


def test_missing_knowledge_names_every_domain_plus_success_definition_and_world_leaders():
    framework = build_research_framework(_GOAL)
    text = " ".join(framework.missing_knowledge)
    assert "success_definition" in text
    assert "current_world_leaders" in text
    for domain in INTELLIGENCE_DOMAINS:
        assert domain in text


def test_research_priority_defaults_to_the_real_stated_order():
    framework = build_research_framework(_GOAL)
    assert framework.research_priority == DEFAULT_RESEARCH_PRIORITY
    assert set(framework.research_priority) == INTELLIGENCE_DOMAINS


def test_created_at_uses_the_injected_time_service():
    ts = TimeService(clock=lambda: _NOW)
    framework = build_research_framework(_GOAL, ts)
    assert framework.created_at == _NOW.isoformat()


def test_does_not_collect_or_analyze_intelligence():
    # Structural, not just documentary: this module must never IMPORT
    # KnowledgeBase, IntelligenceIndex, or collect_intelligence -- proven
    # by parsing its own real source's AST (so a mention in a docstring
    # explaining *why* it doesn't use them, e.g. this module's own
    # opening comment, is never mistaken for a real import), the same
    # "prove it in code, not just prose" discipline already used to
    # structurally prove LocalFolderProvider has no write capability.
    module_path = Path(__file__).resolve().parents[2] / "src" / "atlas" / "brain" / "intelligence_research_framework.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)

    forbidden = {"KnowledgeBase", "IntelligenceIndex", "collect_intelligence"}
    assert not (imported_names & forbidden), f"intelligence_research_framework.py must never import {imported_names & forbidden}"


def test_build_research_framework_never_writes_any_real_file(tmp_path, monkeypatch):
    # Purely computed, no side effects -- run it from an empty cwd and
    # confirm nothing appears on disk.
    monkeypatch.chdir(tmp_path)
    build_research_framework(_GOAL)
    assert list(tmp_path.rglob("*")) == []
