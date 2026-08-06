import json
import subprocess
from unittest.mock import patch

import pytest

from atlas.integrations.claude_provider import ClaudeCLIError, ClaudeProvider, send_task

# The real, observed response envelope from a real, live `claude -p
# ... --output-format json` call made before this module was written
# -- fields trimmed to the ones this connector actually reads.
_REAL_SUCCESS_ENVELOPE = {
    "is_error": False,
    "duration_api_ms": 5974,
    "num_turns": 1,
    "stop_reason": "end_turn",
    "session_id": "76e4c1f3-17d2-436e-86d6-d4e7e77ef2db",
    "total_cost_usd": 0.3353389,
    "subtype": "success",
    "result": "PONG",
    "type": "result",
    "duration_ms": 4911,
    "uuid": "f18698af-bd3a-403f-8cd2-ce7404ed579c",
}


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_a_real_successful_call_returns_the_real_payload_unrenamed():
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(_REAL_SUCCESS_ENVELOPE))) as mock_run:
        payload = send_task("Reply with exactly the single word: PONG")

    assert payload["result"] == "PONG"
    assert payload["is_error"] is False
    assert payload["session_id"] == "76e4c1f3-17d2-436e-86d6-d4e7e77ef2db"
    args = mock_run.call_args.args[0]
    assert args == ["claude", "-p", "Reply with exactly the single word: PONG", "--output-format", "json"]


def test_raises_on_an_empty_task():
    with pytest.raises(ValueError, match="non-empty task"):
        send_task("")


def test_raises_on_a_whitespace_only_task():
    with pytest.raises(ValueError, match="non-empty task"):
        send_task("   ")


def test_raises_when_the_cli_is_not_installed():
    with patch("subprocess.run", side_effect=FileNotFoundError("no such file")):
        with pytest.raises(ClaudeCLIError, match="not found on PATH"):
            send_task("a real task")


def test_raises_on_a_real_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120.0)):
        with pytest.raises(ClaudeCLIError, match="did not respond within"):
            send_task("a real task")


def test_raises_on_a_non_zero_exit_code():
    with patch("subprocess.run", return_value=_FakeCompletedProcess(returncode=1, stderr="real permission error")):
        with pytest.raises(ClaudeCLIError, match="real permission error"):
            send_task("a real task")


def test_raises_on_malformed_json_stdout():
    # Real observed behavior: a workspace-trust warning can appear
    # alongside the JSON -- if it ever ends up on stdout and corrupts
    # the JSON, this must surface loudly, never silently parse partial
    # garbage as a real result.
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout="Ignoring 12 permissions.allow entries...\n{\"result\": \"PONG\"")):
        with pytest.raises(ClaudeCLIError, match="non-JSON stdout"):
            send_task("a real task")


def test_raises_on_an_unexpected_response_type():
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps({"type": "system", "is_error": False}))):
        with pytest.raises(ClaudeCLIError, match="unexpected response type"):
            send_task("a real task")


def test_raises_when_the_cli_itself_reports_a_real_error():
    envelope = dict(_REAL_SUCCESS_ENVELOPE, is_error=True, result="real API error message")
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(envelope))):
        with pytest.raises(ClaudeCLIError, match="real API error message"):
            send_task("a real task")


def test_claude_provider_complete_returns_the_real_result_text():
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(_REAL_SUCCESS_ENVELOPE))):
        result = ClaudeProvider().complete("Reply with exactly the single word: PONG")

    assert result == "PONG"


def test_claude_provider_name_is_claude():
    assert ClaudeProvider().name == "claude"


def test_claude_provider_complete_propagates_a_real_cli_failure():
    with patch("subprocess.run", side_effect=FileNotFoundError("no such file")):
        with pytest.raises(ClaudeCLIError, match="not found on PATH"):
            ClaudeProvider().complete("a real prompt")


def test_claude_provider_complete_structured_parses_a_real_plain_json_response():
    envelope = dict(_REAL_SUCCESS_ENVELOPE, result='{"heading": "Example Domain"}')
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(envelope))):
        result = ClaudeProvider().complete_structured("extract the heading", {"heading": "the main heading"})

    assert result == {"heading": "Example Domain"}


def test_claude_provider_complete_structured_tolerates_a_markdown_fenced_response():
    # The same real LLM quirk this codebase already hit once for
    # Gemini's raw-JSON path (before it moved to native structured
    # output) -- Claude has no equivalent native structured-output
    # parameter, so this path must tolerate it directly.
    fenced = '```json\n{"heading": "Example Domain"}\n```'
    envelope = dict(_REAL_SUCCESS_ENVELOPE, result=fenced)
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(envelope))):
        result = ClaudeProvider().complete_structured("extract the heading", {"heading": "the main heading"})

    assert result == {"heading": "Example Domain"}


def test_claude_provider_complete_structured_fills_a_missing_field_with_empty_string():
    envelope = dict(_REAL_SUCCESS_ENVELOPE, result='{"heading": "Example Domain"}')
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(envelope))):
        result = ClaudeProvider().complete_structured("extract fields", {"heading": "the heading", "price": "the price"})

    assert result == {"heading": "Example Domain", "price": ""}


def test_claude_provider_complete_structured_raises_on_real_non_json_response():
    envelope = dict(_REAL_SUCCESS_ENVELOPE, result="Sure, here is the heading: Example Domain")
    with patch("subprocess.run", return_value=_FakeCompletedProcess(stdout=json.dumps(envelope))):
        with pytest.raises(ClaudeCLIError, match="not valid JSON"):
            ClaudeProvider().complete_structured("extract the heading", {"heading": "the heading"})


def test_claude_provider_never_routes_through_the_brain_layer_executive_log():
    # Structural: this provider must call the dependency-free
    # send_task directly, never atlas.brain.claude_executive's
    # logging wrapper -- the durable executive-interaction record
    # stays a distinct, existing feature this provider does not
    # reroute (see ClaudeProvider's own docstring).
    import ast
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[2] / "src" / "atlas" / "integrations" / "claude_provider.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)

    assert not any(name == "atlas.brain" or name.startswith("atlas.brain.") for name in imported_names)


def test_never_imports_atlas_brain():
    # Structural, not just documentary: atlas.integrations must stay
    # dependency-free (the standing layering rule this codebase
    # enforces everywhere -- atlas.brain freely imports
    # atlas.integrations, never the reverse).
    import ast
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[2] / "src" / "atlas" / "integrations" / "claude_provider.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)

    assert not any(name == "atlas.brain" or name.startswith("atlas.brain.") for name in imported_names)
