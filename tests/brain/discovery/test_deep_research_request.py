import pytest

from atlas.brain.discovery.deep_research_request import (
    DEEP_RESEARCH_TASK_CATEGORY,
    category_from_deep_research_task,
    deep_research_task_description,
)
from atlas.brain.models import Task


def test_deep_research_task_description_round_trips():
    task = Task(goal_id="g1", description=deep_research_task_description("saas"))
    assert category_from_deep_research_task(task) == "saas"


def test_category_from_deep_research_task_rejects_a_non_deep_research_task():
    task = Task(goal_id="g1", description="some other task")
    with pytest.raises(ValueError, match="not a real deep-research task"):
        category_from_deep_research_task(task)


def test_category_from_deep_research_task_rejects_a_shallow_research_task():
    # A shallow request_research task must never be mistaken for a
    # deep_research one -- the two prefixes are deliberately distinct.
    task = Task(goal_id="g1", description="Research business model category: saas")
    with pytest.raises(ValueError, match="not a real deep-research task"):
        category_from_deep_research_task(task)


def test_deep_research_task_category_constant():
    assert DEEP_RESEARCH_TASK_CATEGORY == "deep_research"
