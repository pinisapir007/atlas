from unittest.mock import patch

import pytest

from atlas.brain.claude_executive import ClaudeExecutiveLog, ClaudeTaskResult, send_task
from atlas.integrations.claude_provider import ClaudeCLIError

_REAL_PAYLOAD = {
    "is_error": False,
    "result": "PONG",
    "session_id": "76e4c1f3-17d2-436e-86d6-d4e7e77ef2db",
    "duration_ms": 4911,
    "total_cost_usd": 0.3353389,
    "num_turns": 1,
    "type": "result",
}


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_send_task_wraps_the_real_payload_into_a_structured_result():
    log = ClaudeExecutiveLog(store=_FakeStore())
    with patch("atlas.brain.claude_executive._send_task_raw", return_value=_REAL_PAYLOAD) as mock_send:
        result = send_task("Reply with exactly the single word: PONG", log=log)

    assert isinstance(result, ClaudeTaskResult)
    assert result.task == "Reply with exactly the single word: PONG"
    assert result.result == "PONG"
    assert result.is_error is False
    assert result.session_id == "76e4c1f3-17d2-436e-86d6-d4e7e77ef2db"
    assert result.duration_ms == 4911
    assert result.total_cost_usd == pytest.approx(0.3353389)
    assert result.num_turns == 1
    assert result.raw == _REAL_PAYLOAD
    mock_send.assert_called_once_with("Reply with exactly the single word: PONG", timeout_seconds=120.0)


def test_send_task_records_the_interaction():
    log = ClaudeExecutiveLog(store=_FakeStore())
    with patch("atlas.brain.claude_executive._send_task_raw", return_value=_REAL_PAYLOAD):
        result = send_task("a real task", log=log)

    recorded = log.interactions()
    assert len(recorded) == 1
    assert recorded[0].id == result.id
    assert recorded[0].result == "PONG"


def test_a_real_cli_failure_propagates_and_is_never_recorded():
    log = ClaudeExecutiveLog(store=_FakeStore())
    with patch("atlas.brain.claude_executive._send_task_raw", side_effect=ClaudeCLIError("real failure")):
        with pytest.raises(ClaudeCLIError, match="real failure"):
            send_task("a real task", log=log)

    assert log.interactions() == []


def test_log_round_trips_multiple_interactions():
    log = ClaudeExecutiveLog(store=_FakeStore())
    with patch("atlas.brain.claude_executive._send_task_raw", return_value=_REAL_PAYLOAD):
        first = send_task("task one", log=log)
        second = send_task("task two", log=log)

    recorded = log.interactions()
    assert {r.id for r in recorded} == {first.id, second.id}
    assert {r.task for r in recorded} == {"task one", "task two"}


def test_send_task_defaults_to_a_real_claude_executive_log_when_none_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("atlas.brain.claude_executive._send_task_raw", return_value=_REAL_PAYLOAD):
        send_task("a real task")

    assert (tmp_path / ".atlas" / "claude_executive_log.json").exists()
