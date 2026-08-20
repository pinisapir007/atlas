from atlas.brain.discovery.exploration_gate import (
    explored_categories,
    exploration_sufficient,
    sourced_finding_count,
    unexplored_categories,
)
from atlas.brain.discovery.taxonomy import BUSINESS_MODEL_CATEGORIES, MIN_CATEGORIES_EXPLORED
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _sourced(category: str, i: int) -> Finding:
    return Finding(source="research", category=category, description=f"signal {i}", evidence=f"https://example.com/{i}")


def test_sourced_finding_count_ignores_unsourced_findings(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced("saas", 1))
    kb.save_finding(Finding(source="research", category="saas", description="no evidence", evidence=""))

    assert sourced_finding_count("saas", kb) == 1


def test_explored_categories_requires_the_same_bar_as_decide(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced("saas", 1))  # only one source -- below MIN_INDEPENDENT_SOURCES (2)

    assert "saas" not in explored_categories(kb)

    kb.save_finding(_sourced("saas", 2))
    assert "saas" in explored_categories(kb)


def test_exploration_not_sufficient_with_too_few_explored_categories(tmp_path):
    kb = _kb(tmp_path)
    for category in BUSINESS_MODEL_CATEGORIES[: MIN_CATEGORIES_EXPLORED - 1]:
        kb.save_finding(_sourced(category, 1))
        kb.save_finding(_sourced(category, 2))

    assert exploration_sufficient(kb) is False


def test_exploration_sufficient_once_enough_categories_clear_the_bar(tmp_path):
    kb = _kb(tmp_path)
    for category in BUSINESS_MODEL_CATEGORIES[:MIN_CATEGORIES_EXPLORED]:
        kb.save_finding(_sourced(category, 1))
        kb.save_finding(_sourced(category, 2))

    assert exploration_sufficient(kb) is True


def test_unexplored_categories_lists_only_categories_below_the_bar(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced("saas", 1))
    kb.save_finding(_sourced("saas", 2))

    missing = unexplored_categories(kb)

    assert "saas" not in missing
    assert "marketplace" in missing
    assert missing == sorted(missing)  # deterministic order
