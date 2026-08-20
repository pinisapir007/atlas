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


def test_skips_goal_with_blocked_task_no_duplicate_created():
    # P0 regression test (2026-08-18): a blocked Task previously did not
    # count as "open work", so the planner recreated an identical Task
    # every tick forever -- live-verified as 1,296 blocked Tasks across 8
    # Goals, the same descriptions duplicated ~150x each over ~3 days.
    goal = Goal(description="Grow revenue", priority=1)
    blocked = Task(goal_id=goal.id, description="Advance goal: Grow revenue", status="blocked")
    assert SimplePlanner().plan([goal], [blocked]) == []


def test_blocked_task_still_prevents_duplication_across_many_ticks():
    # Simulates the real bug scenario across several consecutive ticks:
    # a single blocked Task must never accumulate duplicates no matter how
    # many times plan() runs against the same, unchanged state.
    goal = Goal(description="Grow revenue", priority=1)
    blocked = Task(goal_id=goal.id, description="Advance goal: Grow revenue", status="blocked")
    tasks = [blocked]
    for _ in range(5):
        new_tasks = SimplePlanner().plan([goal], tasks)
        assert new_tasks == []
        tasks = tasks + new_tasks
    assert len(tasks) == 1


def test_done_task_still_allows_a_fresh_task_next_tick():
    # Regression guard: "done" must stay excluded from OPEN_STATUSES --
    # an active Goal is a standing objective that legitimately needs a new
    # task to keep advancing it once the previous one completes.
    goal = Goal(description="Grow revenue", priority=1)
    done = Task(goal_id=goal.id, description="Advance goal: Grow revenue", status="done")
    tasks = SimplePlanner().plan([goal], [done])
    assert len(tasks) == 1
    assert tasks[0].goal_id == goal.id


def test_failed_task_still_allows_a_fresh_task_next_tick():
    # Regression guard: "failed" must stay excluded from OPEN_STATUSES --
    # a genuinely failed attempt is worth retrying, unlike a structurally
    # blocked one (no matching asset exists for the category at all).
    goal = Goal(description="Grow revenue", priority=1)
    failed = Task(goal_id=goal.id, description="Advance goal: Grow revenue", status="failed")
    tasks = SimplePlanner().plan([goal], [failed])
    assert len(tasks) == 1
    assert tasks[0].goal_id == goal.id
