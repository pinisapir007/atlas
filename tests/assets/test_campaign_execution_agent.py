from atlas.assets.campaign_execution.agent import CampaignExecutionAgent
from atlas.campaign.registry import CampaignRegistry
from atlas.campaign.models import Campaign
from atlas.brain.models import Task


def _registry(tmp_path) -> CampaignRegistry:
    return CampaignRegistry(tmp_path / "campaigns.json")


def test_run_returns_a_real_next_step_for_the_matching_campaign(tmp_path):
    registry = _registry(tmp_path)
    campaign = Campaign(business_objective="grow affiliate revenue", product_offer="KetoDNA", goal_id="goal-a")
    registry.save_campaign(campaign)
    agent = CampaignExecutionAgent(campaigns=registry)
    task = Task(goal_id="goal-a", description="Founder review requested")

    result = agent.run(task=task)

    assert result["status"] == "done"
    assert result["campaign_id"] == campaign.id
    assert result["product_offer"] == "KetoDNA"
    assert "KetoDNA" in result["next_step"]
    assert "atlas campaign revenue record" in result["next_step"]


def test_run_never_claims_anything_was_published(tmp_path):
    registry = _registry(tmp_path)
    campaign = Campaign(business_objective="a", product_offer="KetoDNA", goal_id="goal-a")
    registry.save_campaign(campaign)
    agent = CampaignExecutionAgent(campaigns=registry)

    result = agent.run(task=Task(goal_id="goal-a", description="d"))

    assert "published" not in result["next_step"].lower() or "no real publishing" in result["next_step"].lower()


def test_run_with_no_matching_campaign_is_honest_not_a_crash(tmp_path):
    registry = _registry(tmp_path)
    agent = CampaignExecutionAgent(campaigns=registry)

    result = agent.run(task=Task(goal_id="goal-does-not-exist", description="d"))

    assert result["status"] == "done"
    assert "no matching campaign" in result["next_step"]


def test_run_with_no_task_is_honest_not_a_crash(tmp_path):
    registry = _registry(tmp_path)
    agent = CampaignExecutionAgent(campaigns=registry)

    result = agent.run()

    assert result["status"] == "done"
    assert "no matching campaign" in result["next_step"]


def test_report_reflects_real_active_campaigns(tmp_path):
    registry = _registry(tmp_path)
    active = Campaign(business_objective="a", goal_id="goal-a", status="active")
    completed = Campaign(business_objective="b", goal_id="goal-b", status="completed")
    registry.save_campaign(active)
    registry.save_campaign(completed)
    agent = CampaignExecutionAgent(campaigns=registry)

    report = agent.report()

    assert report["active_campaigns"] == [active.id]


def test_report_is_computed_fresh_not_cached_across_instances(tmp_path):
    registry = _registry(tmp_path)
    agent_a = CampaignExecutionAgent(campaigns=registry)
    assert agent_a.report()["active_campaigns"] == []

    campaign = Campaign(business_objective="a", goal_id="goal-a", status="active")
    registry.save_campaign(campaign)

    # A brand-new agent instance (simulating a fresh Registry/CLI
    # invocation) must see this real, persisted state, not stale
    # in-memory data from agent_a.
    agent_b = CampaignExecutionAgent(campaigns=registry)
    assert agent_b.report()["active_campaigns"] == [campaign.id]


class _Step3FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_step3_approved_campaign_with_destination_creates_real_hands_request(tmp_path):
    from atlas.brain.memory import BrainMemory
    from atlas.hands.registry import HandsRequestRegistry

    registry = _registry(tmp_path)
    campaign = Campaign(
        business_objective="grow affiliate revenue",
        product_offer="KetoDNA",
        goal_id="goal-step3",
        destination_url="https://example.com",
    )
    registry.save_campaign(campaign)

    memory = BrainMemory(store=_Step3FakeStore())
    hands_requests = HandsRequestRegistry(store=_Step3FakeStore())
    agent = CampaignExecutionAgent(
        campaigns=registry,
        memory=memory,
        hands_requests=hands_requests,
    )

    result = agent.run(
        task=Task(
            goal_id="goal-step3",
            description="Founder approved campaign execution",
        )
    )

    assert result["status"] == "done"
    assert result["hands_request_id"]
    assert result["hands_task_id"]
    assert "published" not in result["next_step"].lower()

    requests = hands_requests.requests()
    assert len(requests) == 1
    request = requests[0]
    assert request.id == result["hands_request_id"]
    assert request.reversible is True
    assert request.steps == [
        {"kind": "navigate", "params": {"url": "https://example.com"}},
        {"kind": "describe_page", "params": {}},
    ]

    tasks = memory.tasks()
    assert len(tasks) == 1
    assert tasks[0].id == request.task_id
    assert tasks[0].category == "hands_execute"
    assert tasks[0].source_opportunity_id == request.id
    assert tasks[0].reversible is True


def test_step3_campaign_hands_bridge_is_idempotent(tmp_path):
    from atlas.brain.memory import BrainMemory
    from atlas.hands.registry import HandsRequestRegistry

    registry = _registry(tmp_path)
    campaign = Campaign(
        business_objective="grow affiliate revenue",
        product_offer="KetoDNA",
        goal_id="goal-step3-idempotent",
        destination_url="https://example.com",
    )
    registry.save_campaign(campaign)

    memory = BrainMemory(store=_Step3FakeStore())
    hands_requests = HandsRequestRegistry(store=_Step3FakeStore())
    agent = CampaignExecutionAgent(
        campaigns=registry,
        memory=memory,
        hands_requests=hands_requests,
    )
    task = Task(
        goal_id="goal-step3-idempotent",
        description="Founder approved campaign execution",
    )

    first = agent.run(task=task)
    second = agent.run(task=task)

    assert first["hands_request_id"] == second["hands_request_id"]
    assert len(hands_requests.requests()) == 1
    assert len(memory.tasks()) == 1
