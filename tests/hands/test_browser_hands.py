from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.hands.browser_hands import BrowserHands, BrowserHandsError


def _fake_action_result(error=None, extracted_content=None):
    return type("R", (), {"error": error, "extracted_content": extracted_content})()


def test_execute_steps_runs_a_real_sequence_in_one_session():
    fake_session = AsyncMock()
    fake_session.downloaded_files = []
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))
    fake_tools.click = AsyncMock(return_value=_fake_action_result(extracted_content="clicked"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands()
        outcome = hands.execute_steps([
            {"kind": "navigate", "params": {"url": "https://example.com"}},
            {"kind": "click", "params": {"index": 1}},
        ])

    assert outcome["results"][0]["success"] is True
    assert outcome["results"][1]["success"] is True
    fake_session.start.assert_awaited_once()
    fake_session.stop.assert_awaited_once()


def test_execute_steps_reports_a_real_step_failure_without_raising():
    fake_session = AsyncMock()
    fake_session.downloaded_files = []
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(error="real navigation error"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands()
        outcome = hands.execute_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}])

    assert outcome["results"][0]["success"] is False
    assert outcome["results"][0]["error"] == "real navigation error"


def test_execute_steps_rejects_an_unrecognized_step_kind():
    fake_session = AsyncMock()

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools"), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands()
        with pytest.raises(BrowserHandsError, match="unrecognized"):
            hands.execute_steps([{"kind": "not_a_real_kind", "params": {}}])

    fake_session.stop.assert_awaited_once()  # cleanup still happens on a real failure


def test_execute_steps_returns_real_downloaded_files():
    fake_session = AsyncMock()
    fake_session.downloaded_files = ["C:/real/downloaded_file.txt"]
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands()
        outcome = hands.execute_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}])

    assert outcome["downloaded_files"] == ["C:/real/downloaded_file.txt"]


def test_name_is_browser_hands():
    assert BrowserHands().name == "browser_hands"
