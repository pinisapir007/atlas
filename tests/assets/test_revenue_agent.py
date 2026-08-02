from atlas.assets.revenue.agent import RevenueAgent
from atlas.brain.models import Task


def test_routes_task_to_the_matching_channel():
    agent = RevenueAgent()
    task = Task(goal_id="g1", description="promote an affiliate offer", category="revenue_affiliate")

    result = agent.run(task=task)

    assert result["status"] == "done"
    assert result["channel"] == "affiliate"


def test_unknown_category_fails_cleanly():
    agent = RevenueAgent()
    task = Task(goal_id="g1", description="mystery work", category="revenue_unknown")

    result = agent.run(task=task)

    assert result["status"] == "failed"


def test_recruitment_leads_are_not_a_revenue_channel():
    # Recruitment/workforce grew into its own operational agent
    # (atlas.assets.recruitment_workforce) — Revenue no longer handles it.
    agent = RevenueAgent()
    task = Task(goal_id="g1", description="source recruitment leads", category="revenue_recruitment_leads")

    result = agent.run(task=task)

    assert result["status"] == "failed"
    assert "revenue_recruitment_leads" not in agent.report()["channels"]


def test_report_aggregates_all_channel_statuses():
    agent = RevenueAgent()
    task = Task(goal_id="g1", description="produce content assets", category="revenue_content_assets")
    agent.run(task=task)

    report = agent.report()

    assert report["status"] == "done"
    assert report["channels"]["revenue_content_assets"]["details"].startswith("queued")
    assert report["channels"]["revenue_affiliate"]["status"] == "idle"
