from datetime import datetime, timedelta, timezone

from atlas.brain.ceo import CEOBrain
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.console import (
    build_briefing,
    build_console_view,
    find_stale_kpis,
    find_warnings,
    format_console_view,
    recent_activity,
    summarize_department_report,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Claim, Opportunity, Proposal, Task
from atlas.brain.opportunities import OpportunityStore
from atlas.core.registry import Registry
from atlas.core.store import JSONStore


def _brain(tmp_path):
    return CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        intelligence_index=IntelligenceIndex(tmp_path / ".atlas" / "intelligence_index.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
    )


def test_view_includes_goals(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1, horizon="short")

    view = build_console_view(brain)

    assert len(view["goals"]) == 1
    assert view["goals"][0]["description"] == "Grow affiliate revenue"
    assert view["goals"][0]["priority"] == 1
    assert view["goals"][0]["horizon"] == "short"


def test_view_includes_pending_approvals_and_excludes_resolved_tasks(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g")
    pending = Task(goal_id=goal.id, description="needs approval", category="x", status="pending_approval")
    done = Task(goal_id=goal.id, description="already done", category="x", status="done")
    brain.memory.save_task(pending)
    brain.memory.save_task(done)

    view = build_console_view(brain)

    ids = {a["id"] for a in view["pending_approvals"]}
    assert ids == {pending.id}


def test_view_includes_blocked_tasks(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g")
    blocked = Task(goal_id=goal.id, description="no capable asset", category="unknown_category", status="blocked")
    brain.memory.save_task(blocked)

    view = build_console_view(brain)

    assert len(view["blocked"]) == 1
    assert view["blocked"][0]["id"] == blocked.id


def test_view_includes_department_reports_for_every_entrypointed_asset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)

    view = build_console_view(brain)

    # Every registered asset with an entrypoint either reports something or
    # is cleanly absent (UnsupportedVerb) — never crashes the console.
    assert "recruitment_workforce" in view["departments"]
    assert "publishing_gateway" in view["departments"]


def test_view_includes_kpis(tmp_path):
    brain = _brain(tmp_path)
    brain.kpis.record("revenue_goal-x", 100.0)

    view = build_console_view(brain)

    assert view["kpis"]["revenue_goal-x"] == 100.0


def test_view_includes_cash_flow_only_for_goals_with_revenue_or_cost(tmp_path):
    brain = _brain(tmp_path)
    tracked = brain.add_goal("Recruitment placements")
    brain.add_goal("Not yet measured")
    brain.kpis.record(f"revenue_{tracked.id}", 1000.0)
    brain.kpis.record(f"cost_{tracked.id}", 400.0)

    view = build_console_view(brain)

    assert len(view["cash_flow"]) == 1
    entry = view["cash_flow"][0]
    assert entry["goal_id"] == tracked.id
    assert entry["profit"] == 600.0
    assert entry["roi"] == 1.5


def test_summarize_department_report_uses_by_stage_or_by_status():
    assert summarize_department_report({"by_stage": {"discovered": 2, "ranked": 0}}) == "{'discovered': 2}"
    assert summarize_department_report({"by_status": {"READY": 1}}) == "{'READY': 1}"
    assert summarize_department_report({"by_stage": {"discovered": 0}}) == "empty"
    assert summarize_department_report({"status": "done"}) == "done"
    assert summarize_department_report("not a dict") == "not a dict"


def test_format_console_view_includes_every_section(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)

    text = format_console_view(build_console_view(brain))

    assert "=== ATLAS Console ===" in text
    assert "Goals (1):" in text
    assert "Grow affiliate revenue" in text
    assert "Departments:" in text
    assert "KPIs:" in text
    assert "Cash Flow:" in text
    assert "(no goal has revenue or cost measured yet)" in text


def test_format_console_view_shows_real_cash_flow_numbers(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("Recruitment placements")
    brain.kpis.record(f"revenue_{goal.id}", 1000.0)
    brain.kpis.record(f"cost_{goal.id}", 400.0)

    text = format_console_view(build_console_view(brain))

    assert "revenue=1000.0 cost=400.0 profit=600.0 roi=1.5" in text


def test_find_stale_kpis_flags_old_readings(tmp_path):
    brain = _brain(tmp_path)
    old_at = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    brain.memory.record_kpi("ancient_metric", 1.0, old_at)
    brain.kpis.record("fresh_metric", 2.0)

    stale = find_stale_kpis(brain, threshold_hours=1.0)

    stale_names = {name for name, _ in stale}
    assert "ancient_metric" in stale_names
    assert "fresh_metric" not in stale_names


def test_find_warnings_detects_maya_stopped_and_revenue_idle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)

    warnings = find_warnings(brain)

    assert any("MAYA is stopped" in w for w in warnings)
    assert any("Revenue channels are idle" in w for w in warnings)


def test_find_warnings_detects_a_pinned_identity_conflict(tmp_path):
    """Test E, warning half (2026-08-17, ONE BRAIN Root Implementation) --
    two already-real Opportunities later linked by a supported
    possibly_same_as Claim must be surfaced, read-only, never merged."""
    from atlas.brain.models import Finding

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    opportunities = OpportunityStore(tmp_path / "opportunities.json")
    brain = CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        intelligence_index=IntelligenceIndex(tmp_path / ".atlas" / "intelligence_index.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
        knowledge=knowledge,
        opportunities=opportunities,
    )
    opportunities.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    opportunities.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))
    link_finding = Finding(source="test", category="affiliate", description="d", evidence="https://x.com/1", subject="prostadine::vendorA")
    knowledge.save_finding(link_finding)
    knowledge.save_claim(Claim(
        subject_id="prostadine::vendorA", predicate="possibly_same_as", object_id="prostadine::vendorB",
        evidence_finding_ids=[link_finding.id],
    ))

    warnings = find_warnings(brain)

    assert any("prostadine::vendorA" in w and "prostadine::vendorB" in w for w in warnings)
    assert len(opportunities.opportunities()) == 2  # untouched


def test_find_warnings_detects_pending_redesign_proposals(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g")
    task = Task(goal_id=goal.id, description="x", category="redesign_workflow")
    brain.memory.save_task(task)
    proposal = Proposal(task_id=task.id, kind="redesign", rationale="KPI flat for 3 periods")
    brain.memory.save_proposal(proposal)

    warnings = find_warnings(brain)

    assert any("KPI flat for 3 periods" in w for w in warnings)


def test_find_warnings_detects_stale_kpis(tmp_path):
    brain = _brain(tmp_path)
    old_at = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    brain.memory.record_kpi("ancient_metric", 1.0, old_at)

    warnings = find_warnings(brain)

    assert any("ancient_metric" in w for w in warnings)


def test_recent_activity_returns_tail_of_log(tmp_path):
    brain = _brain(tmp_path)
    for i in range(15):
        brain.memory.append_log({"event": f"entry-{i}"})

    activity = recent_activity(brain, limit=5)

    assert len(activity) == 5
    assert activity[-1]["event"] == "entry-14"


def test_build_briefing_includes_hebrew_opener_and_current_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)

    briefing = build_briefing(brain)

    assert briefing.startswith("כן פיני")
    assert "Grow affiliate revenue" in briefing
    assert "active goal" in briefing
    assert "need your approval" in briefing


def _counting_build_console_view(monkeypatch, brain):
    """Wraps the real build_console_view with a call counter -- proves a
    function actually reused a passed-in `view`/`warnings` instead of
    silently recomputing it, the real bug found live (2026-08-09) against
    production-scale data: find_warnings/get_system_health/build_briefing
    were each independently recomputing build_console_view() (and, for
    build_briefing, find_warnings() too) from scratch."""
    import atlas.brain.console as console_module

    real_build = console_module.build_console_view
    calls = {"count": 0}

    def counting(b):
        calls["count"] += 1
        return real_build(b)

    monkeypatch.setattr(console_module, "build_console_view", counting)
    return calls


def test_find_warnings_reuses_a_passed_in_view_instead_of_recomputing(tmp_path, monkeypatch):
    brain = _brain(tmp_path)
    view = build_console_view(brain)
    calls = _counting_build_console_view(monkeypatch, brain)

    find_warnings(brain, view)

    assert calls["count"] == 0


def test_find_warnings_computes_its_own_view_when_none_is_passed(tmp_path, monkeypatch):
    brain = _brain(tmp_path)
    calls = _counting_build_console_view(monkeypatch, brain)

    find_warnings(brain)

    assert calls["count"] == 1


def test_get_system_health_reuses_passed_in_warnings(tmp_path):
    from atlas.brain.console import get_system_health

    brain = _brain(tmp_path)
    sentinel_warnings = ["a pre-computed real warning"]

    health = get_system_health(brain, sentinel_warnings)

    assert health["warnings"] == sentinel_warnings


def test_build_briefing_reuses_a_passed_in_view_and_warnings_instead_of_recomputing(tmp_path, monkeypatch):
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)
    view = build_console_view(brain)
    warnings = find_warnings(brain, view)
    calls = _counting_build_console_view(monkeypatch, brain)

    briefing = build_briefing(brain, view, warnings)

    assert calls["count"] == 0
    assert "Grow affiliate revenue" in briefing
