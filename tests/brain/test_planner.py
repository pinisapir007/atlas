from atlas.brain.models import Goal, Task
from atlas.brain.planner import SimplePlanner


def test_emits_one_task_per_active_goal_without_open_work():
    goal = Goal(description="Grow revenue", priority=1)
    tasks = SimplePlanner().plan([goal], [])
    assert len(tasks) == 1
    assert tasks[0].goal_id == goal.id
    assert tasks[0].category == "analyze_revenue"


def test_skips_goal_with_open_task():
    goal = Goal(description="Grow revenue", priority=1)
    existing = Task(goal_id=goal.id, description="already working on it", status="in_progress")
    assert SimplePlanner().plan([goal], [existing]) == []


def test_skips_paused_goal():
    goal = Goal(description="Something", priority=1, status="paused")
    assert SimplePlanner().plan([goal], []) == []


def test_defaults_to_general_category():
    goal = Goal(description="Improve customer happiness", priority=2)
    tasks = SimplePlanner().plan([goal], [])
    assert tasks[0].category == "general"


def test_campaign_keyword_maps_to_launch_campaign():
    goal = Goal(description="Launch a new campaign", priority=2)
    tasks = SimplePlanner().plan([goal], [])
    assert tasks[0].category == "launch_campaign"
