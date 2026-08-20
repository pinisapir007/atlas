from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.hands.browser_hands import BrowserHands, BrowserHandsError


def _fake_action_result(error=None, extracted_content=None):
    return type("R", (), {"error": error, "extracted_content": extracted_content})()


class _FakeAllowlist:
    """A real, injectable stand-in for BrowserAllowlist -- never a real
    read of .atlas/browser_allowlist.json in these tests."""

    def __init__(self, approved: set[str]):
        self._approved = approved

    def is_approved(self, url_or_domain: str) -> bool:
        return any(domain in url_or_domain for domain in self._approved)


class _BrokenAllowlist:
    """Simulates a real failure loading/reading the policy (e.g. a
    corrupted browser_allowlist.json) -- must cause a refusal, not a
    silent "allow everything"."""

    def is_approved(self, url_or_domain: str) -> bool:
        raise OSError("real, simulated failure reading the policy file")


def test_execute_steps_runs_a_real_sequence_in_one_session():
    fake_session = AsyncMock()
    fake_session.downloaded_files = []
    fake_session.get_current_page_url = AsyncMock(return_value="https://example.com")
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))
    fake_tools.click = AsyncMock(return_value=_fake_action_result(extracted_content="clicked"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"example.com"}))
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
    fake_session.get_current_page_url = AsyncMock(return_value="https://example.com")
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(error="real navigation error"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"example.com"}))
        outcome = hands.execute_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}])

    assert outcome["results"][0]["success"] is False
    assert outcome["results"][0]["error"] == "real navigation error"


def test_execute_steps_rejects_an_unrecognized_step_kind():
    fake_session = AsyncMock()

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools"), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"example.com"}))
        with pytest.raises(BrowserHandsError, match="unrecognized"):
            hands.execute_steps([{"kind": "not_a_real_kind", "params": {}}])

    fake_session.stop.assert_awaited_once()  # cleanup still happens on a real failure


def test_execute_steps_returns_real_downloaded_files():
    fake_session = AsyncMock()
    fake_session.downloaded_files = ["C:/real/downloaded_file.txt"]
    fake_session.get_current_page_url = AsyncMock(return_value="https://example.com")
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"example.com"}))
        outcome = hands.execute_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}])

    assert outcome["downloaded_files"] == ["C:/real/downloaded_file.txt"]


def test_name_is_browser_hands():
    assert BrowserHands(allowlist=_FakeAllowlist(set())).name == "browser_hands"


def test_default_constructor_uses_a_real_fail_closed_allowlist_never_none():
    # No allowlist injected -- must default to a real BrowserAllowlist(),
    # never a bare "no check happens" state.
    from atlas.brain.browser_allowlist import BrowserAllowlist

    hands = BrowserHands()
    assert isinstance(hands._allowlist, BrowserAllowlist)


# --- Domain Policy (P0 Stage 1B) ---------------------------------------


def test_navigate_to_an_unapproved_domain_is_refused_before_it_happens():
    fake_session = AsyncMock()
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"digistore24-app.com"}))
        with pytest.raises(BrowserHandsError, match="not approved"):
            hands.execute_steps([{"kind": "navigate", "params": {"url": "https://evil.example.com"}}])

    # the real navigate call must never have happened at all
    fake_tools.navigate.assert_not_awaited()
    fake_session.stop.assert_awaited_once()  # cleanup still happens


def test_a_redirect_to_an_unapproved_domain_is_caught_after_navigation():
    # The requested URL is approved, but the real, current page after
    # navigation (a real client-side/server redirect) is not -- must
    # still be refused, never trusted based on the originally-requested
    # URL alone.
    fake_session = AsyncMock()
    fake_session.get_current_page_url = AsyncMock(return_value="https://evil.example.com/redirected")
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"digistore24-app.com"}))
        with pytest.raises(BrowserHandsError, match="not approved"):
            hands.execute_steps([{"kind": "navigate", "params": {"url": "https://digistore24-app.com/x"}}])


def test_a_click_triggered_navigation_to_an_unapproved_domain_is_caught():
    # No explicit `navigate` step at all -- a real click that silently
    # moved the session to a different, unapproved real page must still
    # be caught, not only an explicit navigate step.
    fake_session = AsyncMock()
    fake_session.get_current_page_url = AsyncMock(return_value="https://evil.example.com")
    fake_tools = MagicMock()
    fake_tools.click = AsyncMock(return_value=_fake_action_result(extracted_content="clicked"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_FakeAllowlist({"digistore24-app.com"}))
        with pytest.raises(BrowserHandsError, match="not approved"):
            hands.execute_steps([{"kind": "click", "params": {"index": 1}}])


def test_hands_fails_closed_when_the_domain_policy_itself_cannot_be_read():
    fake_session = AsyncMock()
    fake_tools = MagicMock()
    fake_tools.navigate = AsyncMock(return_value=_fake_action_result(extracted_content="navigated"))

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.tools.service.Tools", return_value=fake_tools), \
         patch("browser_use.filesystem.file_system.FileSystem"):
        hands = BrowserHands(allowlist=_BrokenAllowlist())
        with pytest.raises(BrowserHandsError, match="fail-closed"):
            hands.execute_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}])

    fake_tools.navigate.assert_not_awaited()  # never even attempted -- policy failure blocks before the action
