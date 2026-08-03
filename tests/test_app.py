from atlas.app import _normalize, run_app
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.ceo import CEOBrain
from atlas.brain.decisions import DecisionLog
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.campaign.registry import CampaignRegistry
from atlas.core.registry import Registry
from atlas.core.store import JSONStore
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry


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
    )


def _capture():
    lines = []
    return lines, lines.append


def test_normalize_maps_natural_language_onto_existing_commands():
    assert _normalize("How are we doing?") == "status"
    assert _normalize("what needs my attention") == "approvals"
    assert _normalize("Anything urgent!") == "warnings"
    assert _normalize("bye") == "exit"


def test_normalize_passes_through_unrecognized_and_original_commands_unchanged():
    assert _normalize("status") == "status"
    assert _normalize("approve task-123") == "approve task-123"
    assert _normalize("something nobody would ever say") == "something nobody would ever say"


def test_run_app_shows_logo_and_greeting_then_processes_commands(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)
    lines, printer = _capture()

    run_app(brain=brain, input_lines=["status", "exit"], speak_enabled=False, print_fn=printer, clear_fn=lambda: None)

    output = "\n".join(lines)
    assert "A T L A S" in output
    assert "CEO Operating System" in output
    assert "כן פיני" in output  # the briefing greeting appears in the transcript
    assert "Grow affiliate revenue" in output
    assert "=== ATLAS Console ===" in output  # the "status" command's output made it in


def test_run_app_natural_language_approval_review(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g", priority=1)
    task = Task(goal_id=goal.id, description="risky", category="reallocate_budget", estimated_amount=5000)
    brain.memory.save_task(task)
    brain.tick()
    lines, printer = _capture()

    run_app(
        brain=brain,
        input_lines=["what needs my attention?", f"approve {task.id}", "exit"],
        speak_enabled=False,
        print_fn=printer,
        clear_fn=lambda: None,
    )

    reloaded = brain.memory.get_task(task.id)
    assert reloaded.status in ("delegated", "done")  # the real approve() logic actually ran
    output = "\n".join(lines)
    assert task.id in output


def test_run_app_never_calls_real_clear_when_clear_fn_provided(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr("atlas.app.os.system", lambda *_: called.append("real clear called"))
    brain = _brain(tmp_path)

    run_app(brain=brain, input_lines=["exit"], speak_enabled=False, print_fn=lambda *_: None, clear_fn=lambda: None)

    assert called == []


def test_run_app_speaks_the_briefing_when_enabled(tmp_path, monkeypatch):
    import atlas.app as app_module

    spoken = []
    monkeypatch.setattr(app_module, "speak", lambda text: spoken.append(text))
    brain = _brain(tmp_path)

    run_app(brain=brain, input_lines=["exit"], speak_enabled=True, print_fn=lambda *_: None, clear_fn=lambda: None)

    assert len(spoken) == 1
    assert spoken[0].startswith("כן פיני")


def test_run_app_never_speaks_when_disabled(tmp_path, monkeypatch):
    import atlas.app as app_module

    spoken = []
    monkeypatch.setattr(app_module, "speak", lambda text: spoken.append(text))
    brain = _brain(tmp_path)

    run_app(brain=brain, input_lines=["exit"], speak_enabled=False, print_fn=lambda *_: None, clear_fn=lambda: None)

    assert spoken == []


def test_run_app_voice_command_uses_listen_and_feeds_result_to_dispatch(tmp_path, monkeypatch):
    import atlas.app as app_module

    monkeypatch.setattr(app_module, "listen", lambda timeout_seconds=8: "how are we doing")
    brain = _brain(tmp_path)
    brain.add_goal("Grow affiliate revenue", priority=1)
    lines, printer = _capture()

    run_app(
        brain=brain,
        input_lines=["voice", "exit"],
        speak_enabled=False,
        listen_enabled=True,
        print_fn=printer,
        clear_fn=lambda: None,
    )

    output = "\n".join(lines)
    assert "=== ATLAS Console ===" in output  # "how are we doing" -> "status" -> its output appeared


def test_run_app_voice_gracefully_degrades_when_nothing_is_heard(tmp_path, monkeypatch):
    import atlas.app as app_module

    monkeypatch.setattr(app_module, "listen", lambda timeout_seconds=8: None)
    brain = _brain(tmp_path)
    lines, printer = _capture()

    run_app(
        brain=brain,
        input_lines=["voice", "exit"],
        speak_enabled=False,
        listen_enabled=True,
        print_fn=printer,
        clear_fn=lambda: None,
    )

    assert any("voice input unavailable" in line for line in lines)


def test_run_app_voice_command_ignored_when_listen_disabled(tmp_path):
    # "voice" is only special-cased when listen_enabled=True; otherwise it's
    # just an unrecognized command, same as anything else.
    brain = _brain(tmp_path)
    lines, printer = _capture()

    run_app(
        brain=brain,
        input_lines=["voice", "exit"],
        speak_enabled=False,
        listen_enabled=False,
        print_fn=printer,
        clear_fn=lambda: None,
    )

    output = "\n".join(lines)
    assert "unknown command" in output


def test_run_app_stops_cleanly_when_scripted_input_is_exhausted(tmp_path):
    brain = _brain(tmp_path)
    lines, printer = _capture()

    run_app(brain=brain, input_lines=["status"], speak_enabled=False, print_fn=printer, clear_fn=lambda: None)

    assert "=== ATLAS Console ===" in "\n".join(lines)
