from starlette.testclient import TestClient

from atlas.brain.ceo import CEOBrain
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.decisions import DecisionLog
from atlas.brain.investigations import InvestigationStore
from atlas.brain.ledger import Ledger
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.brain.conversation_memory import ConversationMemory
from atlas.brain.opportunities import OpportunityStore
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
        opportunities=OpportunityStore(store=_FakeStore()),
        marketplace_catalog=MarketplaceCatalogStore(store=_FakeStore()),
        investigations=InvestigationStore(store=_FakeStore()),
    )


def test_index_serves_real_html(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.get("/")

    assert response.status_code == 200
    assert "ATLAS Headquarters" in response.text
    assert "text/html" in response.headers["content-type"]


def test_platform_connections_are_honest_never_a_fabricated_connected_status(tmp_path, monkeypatch):
    # The founder's explicit instruction (2026-08-09): never show a
    # platform as connected unless it genuinely is. digistore24 is the
    # one real CommerceProvider -- its status must be "code_ready" (real
    # class, no credential) unless DIGISTORE24_API_KEY is actually set in
    # this environment, and must flip to "connected" the moment it is --
    # a live, real check, never a hardcoded assumption either way.
    import atlas.headquarters.server as server_module

    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    connections = {c["id"]: c for c in server_module._real_platform_connections()}
    assert connections["digistore24"]["status"] == "code_ready"

    monkeypatch.setenv("DIGISTORE24_API_KEY", "a-real-looking-key")
    connections = {c["id"]: c for c in server_module._real_platform_connections()}
    assert connections["digistore24"]["status"] == "connected"

    # every named-but-unbuilt platform is always "not_built" -- never
    # flips to connected just because it's listed
    for placeholder_id in ("amazon_associates", "youtube", "shopify"):
        assert connections[placeholder_id]["status"] == "not_built"


def test_api_state_includes_platform_connections(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.get("/api/state")
    data = response.json()

    assert len(data["platform_connections"]) >= 10
    assert all("status" in c and c["status"] in {"connected", "code_ready", "not_built"} for c in data["platform_connections"])


def test_real_state_calls_build_console_view_exactly_once(tmp_path, monkeypatch):
    # Real bug, found live (2026-08-09) against real production-scale
    # data (1771 tasks, a 10MB brain.json): _real_state() used to call
    # find_warnings()/get_system_health()/build_briefing() with no
    # arguments, and each of those independently recomputed
    # build_console_view() (and, for build_briefing, find_warnings() too)
    # from scratch -- 5 total build_console_view() calls per single
    # _real_state() invocation, several real seconds each at that scale.
    # Since the SSE stream re-runs _real_state() every 5 seconds for as
    # long as a real browser tab is connected, this made the entire
    # server unable to answer even the plain index page. Guards against
    # the redundancy silently creeping back in.
    import atlas.headquarters.server as server_module

    brain = _isolated_brain(tmp_path)
    real_build = server_module.build_console_view
    calls = {"count": 0}

    def counting(b):
        calls["count"] += 1
        return real_build(b)

    monkeypatch.setattr(server_module, "build_console_view", counting)

    server_module._real_state(brain)

    assert calls["count"] == 1


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
    assert data["atlas_last_active"] is None


def test_api_state_active_asset_ids_reflects_real_in_flight_tasks(tmp_path):
    brain = _isolated_brain(tmp_path)
    goal = Goal(description="g", status="active")
    brain.memory.save_goal(goal)
    in_flight = Task(goal_id=goal.id, description="dispatched work", assigned_asset_id="research")
    in_flight.status = "delegated"
    brain.memory.save_task(in_flight)
    done = Task(goal_id=goal.id, description="finished work", assigned_asset_id="maya")
    done.status = "done"
    brain.memory.save_task(done)
    client = TestClient(create_app(brain))

    response = client.get("/api/state")
    data = response.json()

    assert data["active_asset_ids"] == ["research"]


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
    # ATLAS's own recorded action timestamp, not the moment this request
    # happened to be made -- the real signal the founder relies on to see
    # ATLAS was working while they were away.
    assert data["atlas_last_active"] == data["decisions"][0]["created_at"]


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


def test_api_tick_runs_a_real_cycle_and_returns_fresh_state(tmp_path):
    brain = _isolated_brain(tmp_path)
    brain.memory.save_goal(Goal(description="a real active goal", status="active"))
    client = TestClient(create_app(brain))

    response = client.post("/api/tick")
    data = response.json()

    assert response.status_code == 200
    assert "goals" in data and "briefing" in data


def test_api_review_returns_a_real_report_for_a_valid_period(tmp_path):
    brain = _isolated_brain(tmp_path)
    brain.memory.save_goal(Goal(description="a real active goal", status="active"))
    client = TestClient(create_app(brain))

    response = client.post("/api/review/daily")
    data = response.json()

    assert response.status_code == 200
    assert data["period"] == "daily"
    assert "a real active goal" in data["active_goals"]


def test_api_review_rejects_an_invalid_period(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain))

    response = client.post("/api/review/not-a-real-period")

    assert response.status_code == 400
    assert "error" in response.json()


class _FakeAIProvider:
    """Fake for the real AIProvider Protocol -- a real Claude CLI call
    costs real money and real seconds, so tests never make one."""

    name = "fake"

    def __init__(self, reply: str = "Good morning. Here is what I did.", raise_error: bool = False):
        self._reply = reply
        self._raise_error = raise_error
        self.last_prompt = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        if self._raise_error:
            raise RuntimeError("simulated real backend failure")
        return self._reply

    def complete_structured(self, prompt: str, fields: dict) -> dict:
        raise NotImplementedError


def test_api_converse_returns_a_real_grounded_reply_and_records_it(tmp_path):
    brain = _isolated_brain(tmp_path)
    goal = Goal(description="grow the real keto affiliate business", status="active")
    brain.memory.save_goal(goal)
    task = Task(goal_id=goal.id, description="launch the top-ranked influencer", reversible=False, category="hands_execute")
    task.status = "pending_approval"
    brain.memory.save_task(task)
    fake_ai = _FakeAIProvider(reply="Good morning. One item awaits your approval.")
    client = TestClient(create_app(brain, ai_provider=fake_ai))

    response = client.post("/api/converse", json={"message": "בוקר טוב, מה קרה?"})
    data = response.json()

    assert response.status_code == 200
    assert data["reply"] == "Good morning. One item awaits your approval."
    # the real pending approval's own description was actually included
    # in the grounding context sent to the real backend -- not a blind call
    assert "launch the top-ranked influencer" in fake_ai.last_prompt
    assert "בוקר טוב" in fake_ai.last_prompt
    recorded = brain.conversations.recent(limit=1)
    assert recorded[0].input_line == "בוקר טוב, מה קרה?"
    assert recorded[0].response_summary == "Good morning. One item awaits your approval."


def test_api_converse_rejects_an_empty_message(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain, ai_provider=_FakeAIProvider()))

    response = client.post("/api/converse", json={"message": "   "})

    assert response.status_code == 400
    assert "error" in response.json()


def test_api_converse_is_honest_about_a_real_backend_failure(tmp_path):
    brain = _isolated_brain(tmp_path)
    client = TestClient(create_app(brain, ai_provider=_FakeAIProvider(raise_error=True)))

    response = client.post("/api/converse", json={"message": "hello"})

    assert response.status_code == 502
    assert "ATLAS is not reachable" in response.json()["error"]
    assert brain.conversations.recent() == []


def test_api_conversations_reflects_real_recorded_turns(tmp_path):
    brain = _isolated_brain(tmp_path)
    brain.conversations.record_turn("hello ATLAS", "hello, founder")
    client = TestClient(create_app(brain, ai_provider=_FakeAIProvider()))

    response = client.get("/api/conversations")
    data = response.json()

    assert response.status_code == 200
    assert len(data["entries"]) == 1
    assert data["entries"][0]["input_line"] == "hello ATLAS"



def test_health_returns_200_when_core_state_is_readable(tmp_path):
    brain = _isolated_brain(tmp_path)
    brain.memory.save_goal(
        Goal(description="health qualification goal", status="active")
    )

    client = TestClient(create_app(brain))
    response = client.get("/health")
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "ok"
    assert data["service"] == "atlas-headquarters"
    assert data["checks"]["memory"]["status"] == "ok"
    assert data["checks"]["memory"]["goals_readable"] == 1
    assert data["checks"]["ledger"]["status"] == "ok"


def test_health_returns_503_when_core_state_cannot_be_read(tmp_path, monkeypatch):
    brain = _isolated_brain(tmp_path)

    def broken_goals():
        raise OSError("simulated unreadable state")

    monkeypatch.setattr(brain.memory, "goals", broken_goals)

    client = TestClient(create_app(brain))
    response = client.get("/health")
    data = response.json()

    assert response.status_code == 503
    assert data["status"] == "unhealthy"
    assert data["checks"]["memory"]["status"] == "error"
    assert data["checks"]["memory"]["error_type"] == "OSError"
    assert data["checks"]["ledger"]["status"] == "ok"
