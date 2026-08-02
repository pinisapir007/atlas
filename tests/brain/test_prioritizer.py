from atlas.brain.models import Goal, Task
from atlas.brain.prioritizer import SimplePrioritizer


def test_higher_goal_priority_scores_higher():
    high_goal = Goal(description="high", priority=1)
    low_goal = Goal(description="low", priority=5)
    high_task = Task(goal_id=high_goal.id, description="a")
    low_task = Task(goal_id=low_goal.id, description="b")
    goals_by_id = {high_goal.id: high_goal, low_goal.id: low_goal}

    SimplePrioritizer().score([high_task, low_task], goals_by_id)

    assert high_task.priority_score > low_task.priority_score


def test_large_amount_is_penalized():
    goal = Goal(description="g", priority=1)
    cheap = Task(goal_id=goal.id, description="cheap", estimated_amount=0)
    expensive = Task(goal_id=goal.id, description="expensive", estimated_amount=20_000)
    goals_by_id = {goal.id: goal}

    SimplePrioritizer().score([cheap, expensive], goals_by_id)

    assert cheap.priority_score > expensive.priority_score


def test_unknown_goal_gets_zero_weight():
    task = Task(goal_id="missing", description="orphan")
    SimplePrioritizer().score([task], {})
    assert task.priority_score >= 0
