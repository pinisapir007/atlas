from starlette.testclient import TestClient

from atlas.brain.ceo import CEOBrain
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.decisions import DecisionLog
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.brain.conversation_memory import ConversationMemory
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.registry import InfluencerRegistry
from atlas.brand.registry import BrandRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry
from atlas.assets.affiliate_intelligence.agent import AffiliateStore
from atlas.core.registry import Registry
from atlas.headquarters.server import create_app


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeAssetStore:
    """Fake for atlas.core.store.Store's real get(asset_id)/set(asset_id,
    state) protocol -- distinct from BrainStore's read()/write() shape
    used by every brain-layer registry above."""

    def __init__(self):
        self._data = {}

    def get(self, asset_id):
        return self._data.get(asset_id, {})

    def set(self, asset_id, state):
        self._data[asset_id] = state


def _isolated_brain(tmp_path) -> CEOBrain:
    """A real CEOBrain with every registry pointed at a real, isolated
    in-memory fake store (or a real scratch tmp_path file, for the one
    store that has no injectable-store constructor) -- never the real
    production .atlas/ paths. Mirrors the exact isolation discipline
    every other Mission's live validation already established (and the
    real bug it was originally caught fixing)."""
    return CEOBrain(
        memory=BrainMemory(store=_FakeStore()),
        registry=Registry(store=_FakeAssetStore()),
        knowledge=KnowledgeBase(store=_FakeStore()),
        decisions=DecisionLog(store=_FakeStore()),
        ledger=Ledger(store=_FakeStore()),
        campaigns=CampaignRegistry(store=_FakeStore()),
        influencers=InfluencerRegistry(store=_FakeStore()),
        brands=BrandRegistry(store=_FakeStore()),
        execution_plans=ExecutionPlanRegistry(store=_FakeStore()),
        affiliate_store=AffiliateStore(tmp_path / "affiliate_intelligence.json"),
        conversations=ConversationMemory(store=_FakeStore()),
    )


def test_index_serves_real_html(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.get("/")

    assert response.status_code == 200
    assert "ATLAS Headquarters" in response.text
    assert "text/html" in response.headers["content-type"]


def test_api_state_reflects_a_real_goal(tmp_path):
    brain = _isolated_brain(tmp_path)
    brain.memory.save_goal(Goal(description="grow the real keto business", status="active"))
    client = TestClient(create_app(brain))

    response = client.get("/api/state")
    data = response.json()

    assert response.status_code == 200
    assert len(data["goals"]) == 1
    assert data["goals"][0]["description"] == "grow the real keto business"
    assert "briefing" in data
    assert data["decisions"] == []
    assert data["success_laws"] == []


def test_api_state_departments_are_pre_summarized_never_raw_json_only(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.get("/api/state")
    data = response.json()

    for report in data["departments"].values():
        assert "summary" in report and "raw" in report


def test_api_state_reflects_a_real_decision(tmp_path):
    from atlas.brain.decisions import Decision

    brain = _isolated_brain(tmp_path)
    brain.decisions.save_decision(Decision(category="affiliate", verdict="invest", confidence=0.8, factors={}, reasoning="real evidence"))
    client = TestClient(create_app(brain))

    response = client.get("/api/state")
    data = response.json()

    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["category"] == "affiliate"
    assert data["decisions"][0]["verdict"] == "invest"


def test_api_state_reflects_a_real_success_law_track_record(tmp_path):
    from atlas.brain.models import SuccessLaw

    brain = _isolated_brain(tmp_path)
    law = SuccessLaw(principle="personalization beats generic advice", source_description="real evidence", evidence_finding_ids=[])
    brain.knowledge.save_success_law(law)
    client = TestClient(create_app(brain))

    response = client.get("/api/state")
    data = response.json()

    assert len(data["success_laws"]) == 1
    assert data["success_laws"][0]["principle"] == "personalization beats generic advice"
    assert data["success_laws"][0]["evidence_backed"] is False
    assert data["success_laws"][0]["track_record"] is None


def test_api_approve_resolves_a_real_pending_task(tmp_path):
    brain = _isolated_brain(tmp_path)
    goal = Goal(description="g", status="active")
    brain.memory.save_goal(goal)
    task = Task(goal_id=goal.id, description="real risky task", reversible=False)
    brain.memory.save_task(task)
    client = TestClient(create_app(brain))

    response = client.post(f"/api/approve/{task.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == task.id
    updated = [t for t in brain.memory.tasks() if t.id == task.id][0]
    assert updated.status != "pending_approval"


def test_api_approve_unknown_task_is_honest_not_a_crash(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.post("/api/approve/does-not-exist")

    assert response.status_code == 404
    assert "error" in response.json()


def test_api_reject_resolves_a_real_pending_task(tmp_path):
    brain = _isolated_brain(tmp_path)
    goal = Goal(description="g", status="active")
    brain.memory.save_goal(goal)
    task = Task(goal_id=goal.id, description="real risky task", reversible=False)
    brain.memory.save_task(task)
    client = TestClient(create_app(brain))

    response = client.post(f"/api/reject/{task.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "failed"


def test_api_recall_finds_a_real_goal(tmp_path):
    brain = _isolated_brain(tmp_path)
    brain.memory.save_goal(Goal(description="grow the keto affiliate business", status="active"))
    client = TestClient(create_app(brain))

    response = client.get("/api/recall?q=keto")
    data = response.json()

    assert response.status_code == 200
    assert len(data["hits"]) >= 1
    assert any(h["store"] == "goal" for h in data["hits"])


def test_api_recall_with_no_query_returns_empty(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.get("/api/recall")

    assert response.json() == {"hits": []}


def test_default_brain_is_created_when_none_injected():
    # Confirms create_app() doesn't require an explicit brain -- but this
    # test never calls any route, so it never touches real production
    # state, only constructs the object.
    app = create_app()
    assert app is not None
