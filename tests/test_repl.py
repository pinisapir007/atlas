from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.ceo import CEOBrain
from atlas.brain.decisions import DecisionLog
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.opportunities import OpportunityStore
from atlas.campaign.registry import CampaignRegistry
from atlas.core.registry import Registry
from atlas.core.store import JSONStore
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry
from atlas.repl import dispatch, run_repl


def _brain(tmp_path):
    return CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
        knowledge=KnowledgeBase(tmp_path / "knowledge.json"),
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
        campaigns=CampaignRegistry(tmp_path / ".atlas" / "campaigns.json"),
        influencers=InfluencerRegistry(tmp_path / ".atlas" / "influencers.json"),
        execution_plans=ExecutionPlanRegistry(tmp_path / ".atlas" / "execution_plans.json"),
        affiliate_store=AffiliateStore(tmp_path / ".atlas" / "affiliate_intelligence.json"),
        opportunities=OpportunityStore(tmp_path / ".atlas" / "opportunities.json"),
        marketplace_catalog=MarketplaceCatalogStore(tmp_path / ".atlas" / "marketplace_catalog.json"),
        investigations=InvestigationStore(tmp_path / ".atlas" / "investigations.json"),
    )


def _capture():
    lines = []
    return lines, lines.append


def test_status_command_prints_console_view(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)
    lines, printer = _capture()

    dispatch(brain, "status", print_fn=printer)

    output = "\n".join(lines)
    assert "=== ATLAS Console ===" in output
    assert "Grow affiliate revenue" in output


def test_briefing_command(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "briefing", print_fn=printer)

    assert lines[0].startswith("כן פיני")


def test_approve_calls_existing_brain_approve_logic_not_a_duplicate(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g", priority=1)
    task = Task(goal_id=goal.id, description="risky", category="reallocate_budget", estimated_amount=5000)
    brain.memory.save_task(task)
    brain.tick()
    assert brain.memory.get_task(task.id).status == "pending_approval"
    lines, printer = _capture()

    dispatch(brain, f"approve {task.id}", print_fn=printer)

    reloaded = brain.memory.get_task(task.id)
    # 2026-08-15, Delegator Fail-Closed Fix: "reallocate_budget" matches no
    # asset with a real entrypoint (`cfo` is registered metadata-only) --
    # dispatch() still called the real brain.approve() logic (that's what
    # this test proves), it now honestly reports blocked instead of an
    # unrelated fallback.
    assert reloaded.status == "blocked"
    assert f"{task.id} ->" in lines[0]


def test_reject_calls_existing_brain_reject_logic(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g", priority=1)
    task = Task(goal_id=goal.id, description="risky", category="reallocate_budget", estimated_amount=5000)
    brain.memory.save_task(task)
    brain.tick()
    lines, printer = _capture()

    dispatch(brain, f"reject {task.id}", print_fn=printer)

    assert brain.memory.get_task(task.id).status == "failed"


def test_approve_without_id_shows_usage(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "approve", print_fn=printer)

    assert "usage: approve" in lines[0]


def test_approve_unknown_id_reports_error_not_crash(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "approve does-not-exist", print_fn=printer)

    assert "error" in lines[0]


def test_warnings_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "warnings", print_fn=printer)

    assert any("MAYA is stopped" in line for line in lines)


def test_activity_command_with_no_activity(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "activity", print_fn=printer)

    assert "No activity" in lines[0]


def test_queue_command_with_empty_queue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "queue", print_fn=printer)

    assert "Queue is empty" in lines[0]


def test_opportunities_command_with_none_yet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "opportunities", print_fn=printer)

    assert "No opportunities yet" in lines[0]


def test_leading_bom_does_not_break_command_parsing(tmp_path):
    # Regression: PowerShell piping stdin as UTF-8-with-BOM prefixed the
    # first line with U+FEFF, so "briefing" was silently read as unknown.
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, chr(0xFEFF) + "briefing", print_fn=printer)

    assert lines[0].startswith("כן פיני")


def test_unknown_command_shows_help(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    dispatch(brain, "banana", print_fn=printer)

    assert "unknown command" in lines[0]
    assert any("Commands:" in line for line in lines)


def test_exit_signals_stop():
    result = dispatch(None, "exit", print_fn=lambda *_: None)
    assert result is False


def test_quit_also_signals_stop():
    result = dispatch(None, "quit", print_fn=lambda *_: None)
    assert result is False


def test_run_repl_greets_then_processes_scripted_commands_then_exits(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)
    lines, printer = _capture()

    run_repl(brain=brain, input_lines=["status", "exit"], speak_enabled=False, print_fn=printer)

    output = "\n".join(lines)
    assert "כן פיני" in output  # the greeting/briefing happened first
    assert "=== ATLAS Console ===" in output  # then the scripted "status" command ran


def test_run_repl_stops_cleanly_when_input_is_exhausted(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    run_repl(brain=brain, input_lines=["status"], speak_enabled=False, print_fn=printer)  # no "exit" — input just ends

    assert "=== ATLAS Console ===" in "\n".join(lines)


def test_run_repl_never_speaks_when_disabled(tmp_path, monkeypatch):
    import atlas.repl as repl_module

    called = []
    monkeypatch.setattr(repl_module, "speak", lambda text: called.append(text))
    brain = _brain(tmp_path)

    run_repl(brain=brain, input_lines=["exit"], speak_enabled=False, print_fn=lambda *_: None)

    assert called == []


def test_run_repl_speaks_the_briefing_when_enabled(tmp_path, monkeypatch):
    import atlas.repl as repl_module

    called = []
    monkeypatch.setattr(repl_module, "speak", lambda text: called.append(text))
    brain = _brain(tmp_path)

    run_repl(brain=brain, input_lines=["exit"], speak_enabled=True, print_fn=lambda *_: None)

    assert len(called) == 1
    assert called[0].startswith("כן פיני")
