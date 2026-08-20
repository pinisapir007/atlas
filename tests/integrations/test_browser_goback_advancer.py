import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.integrations.browser_goback_advancer import VerifiedGoBackAdvancer
from atlas.integrations.browser_use_observer import BrowserUseError

_REAL_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
_LOGIN_URL = "https://www.digistore24.com/login/UL2FwcC9lbi9hZmZpbGlhdGUvYWNjb3VudC9tYXJrZXRwbGFjZS9hbGw_e/?autologin=clear"
_TEXT_BEFORE = "detail page text"
_TEXT_AFTER = "listing page text, changed"


class _FakeEvent:
    def __await__(self):
        async def _noop():
            return None

        return _noop().__await__()

    async def event_result(self, raise_if_any=True, raise_if_none=False):
        return None


def _fake_session(current_url: str = _REAL_URL):
    session = AsyncMock()
    session.get_current_page_url.return_value = current_url
    session.get_state_as_text.return_value = _TEXT_BEFORE
    session.event_bus = MagicMock()
    session.event_bus.dispatch.return_value = _FakeEvent()
    return session


def test_go_back_dispatches_exactly_one_goback_event():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedGoBackAdvancer(cdp_url="http://localhost:9222")
        result = advancer.go_back(verify_target=lambda u: True)

    fake_session.event_bus.dispatch.assert_called_once()
    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert type(dispatched_event).__name__ == "GoBackEvent"
    assert result.url == _REAL_URL


def test_go_back_fails_closed_on_real_login_redirect():
    """The exact, real, live-confirmed incident this class exists to
    prevent: a go-back that lands on a real login/autologin redirect
    must raise, never be treated as a successful return."""
    fake_session = _fake_session(current_url=_LOGIN_URL)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedGoBackAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.go_back(verify_target=lambda u: "digistore24-app.com" in u)


def test_go_back_requires_verify_target_to_actually_be_consulted():
    """verify_target is REQUIRED and always consulted against the real,
    freshly-read post-go-back URL -- never skipped."""
    fake_session = _fake_session()
    calls = []
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedGoBackAdvancer()
        advancer.go_back(verify_target=lambda u: calls.append(u) or True)

    assert calls == [_REAL_URL]


def test_go_back_polls_for_real_content_change():
    fake_session = _fake_session()
    fake_session.get_state_as_text.side_effect = [_TEXT_BEFORE, _TEXT_BEFORE, _TEXT_AFTER, _TEXT_AFTER]
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = VerifiedGoBackAdvancer()
        result = advancer.go_back(
            verify_target=lambda u: True,
            content_changed=lambda t: t == _TEXT_AFTER,
            content_change_timeout=5.0,
        )

    assert result.content_changed is True
    assert result.text_content == _TEXT_AFTER


def test_go_back_content_change_timeout_is_a_legitimate_non_raising_outcome():
    fake_session = _fake_session()
    fake_session.get_state_as_text.return_value = _TEXT_BEFORE  # never changes
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = VerifiedGoBackAdvancer()
        result = advancer.go_back(
            verify_target=lambda u: True,
            content_changed=lambda t: t == _TEXT_AFTER,
            content_change_timeout=0.01,
        )

    assert result.content_changed is False  # a real, reportable fact, not an exception


def test_session_is_always_stopped_even_on_failure():
    fake_session = _fake_session()
    fake_session.event_bus.dispatch.side_effect = RuntimeError("real dispatch failure")
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedGoBackAdvancer()
        with pytest.raises(BrowserUseError):
            advancer.go_back(verify_target=lambda u: True)

    fake_session.stop.assert_awaited_once()


def test_goback_advancer_module_exposes_no_form_input_click_or_navigate_capability():
    """Structural, same discipline as VerifiedClickAdvancer's/
    DiscoveryScrollAdvancer's own tests: this module must never be able
    to do anything except go-back+read -- not even click, since a
    genuine return should never need one."""
    import atlas.integrations.browser_goback_advancer as module

    source = inspect.getsource(module)
    forbidden_code_patterns = (
        "Tools(",
        "from browser_use.tools",
        "import Tools",
        ".input_text(",
        ".upload_file(",
        ".send_keys(",
        ".navigate_to(",
        "ClickElementEvent",
        "TypeTextEvent",
        "SendKeysEvent",
        "UploadFileEvent",
        "NavigateToUrlEvent",
        "BrowserHands",
        "browser_hands",
    )
    for forbidden in forbidden_code_patterns:
        assert forbidden not in source, f"{forbidden!r} must never appear as real code in VerifiedGoBackAdvancer's module"
