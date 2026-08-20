import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from browser_use.dom.views import EnhancedDOMTreeNode, NodeType

from atlas.integrations.browser_button_click_advancer import VerifiedButtonClickAdvancer
from atlas.integrations.browser_use_observer import BrowserUseError

_REAL_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
_BACK_CLASS = "back ng-star-inserted"
_TEXT_BEFORE = "detail page content"
_TEXT_AFTER = "listing content, changed"


class _FakeEvent:
    def __await__(self):
        async def _noop():
            return None

        return _noop().__await__()

    async def event_result(self, raise_if_any=True, raise_if_none=False):
        return None


class _FakeTarget:
    def __init__(self, url: str, target_id: str):
        self.url = url
        self.target_id = target_id


_next_node_id = [1]


def _FakeNode(tag_name: str, attrs: dict | None = None) -> EnhancedDOMTreeNode:
    attributes = dict(attrs or {})
    node_id = _next_node_id[0]
    _next_node_id[0] += 1
    return EnhancedDOMTreeNode(
        node_id=node_id, backend_node_id=node_id, node_type=NodeType.ELEMENT_NODE, node_name=tag_name.upper(),
        node_value="", attributes=attributes, is_scrollable=None, is_visible=True, absolute_position=None,
        target_id="target-1", frame_id=None, session_id=None, content_document=None, shadow_root_type=None,
        shadow_roots=None, parent_node=None, children_nodes=None, ax_node=None, snapshot_node=None,
    )


def _fake_session(selector_map: dict, current_url: str = _REAL_URL):
    session = AsyncMock()
    session.get_current_page_url.return_value = current_url
    session.get_state_as_text.return_value = _TEXT_BEFORE
    session.session_manager = MagicMock()
    session.session_manager.get_all_page_targets.return_value = [_FakeTarget(url=_REAL_URL, target_id="target-1")]
    session.event_bus = MagicMock()
    session.event_bus.dispatch.return_value = _FakeEvent()
    fake_summary = MagicMock()
    fake_summary.dom_state.selector_map = selector_map
    session.get_browser_state_summary = AsyncMock(return_value=fake_summary)
    return session


def _real_back_button_map():
    """The exact, real, live-observed shape (2026-08-17 live diagnostic):
    class='back ng-star-inserted', no href, no type=submit."""
    return {
        1: _FakeNode("button", {"class": _BACK_CLASS}),
        2: _FakeNode("button", {"class": "notifications-center__trigger", "aria-label": "Open notifications"}),
        3: _FakeNode("a", {"href": "https://example.com/detail/123"}),  # not a button, must never count
    }


def test_click_dispatches_exactly_one_click_event_on_the_matched_button():
    fake_session = _fake_session(_real_back_button_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer(cdp_url="http://localhost:9222")
        result = advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_called_once()
    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert type(dispatched_event).__name__ == "ClickElementEvent"
    assert result.clicked_attributes["class"] == _BACK_CLASS


def test_click_fails_closed_with_zero_matching_buttons():
    fake_session = _fake_session(_real_back_button_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError, match="0 matches"):
            advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == "no-such-class", select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_fails_closed_with_more_than_one_distinct_matching_button():
    selector_map = {
        1: _FakeNode("button", {"class": "x", "aria-label": "one"}),
        2: _FakeNode("button", {"class": "x", "aria-label": "two"}),
    }
    fake_session = _fake_session(selector_map)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError, match="[Aa]mbiguous"):
            advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == "x", select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_never_targets_a_type_submit_button_even_if_predicate_would_match():
    """Unconditional defense-in-depth: the caller's own predicate is
    NEVER trusted alone for form-submission-shaped buttons."""
    selector_map = {1: _FakeNode("button", {"class": _BACK_CLASS, "type": "submit"})}
    fake_session = _fake_session(selector_map)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError, match="0 matches"):
            advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_never_targets_a_button_with_form_markers():
    selector_map = {1: _FakeNode("button", {"class": _BACK_CLASS, "name": "submit-form"})}
    fake_session = _fake_session(selector_map)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError, match="0 matches"):
            advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS, select_existing_target=False)


def test_click_fails_closed_when_target_mismatches_before_clicking():
    fake_session = _fake_session(_real_back_button_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS, verify_target=lambda u: False, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_fails_closed_when_target_changes_after_clicking_real_login_redirect():
    fake_session = _fake_session(_real_back_button_map())
    fake_session.get_current_page_url.side_effect = [_REAL_URL, "https://www.digistore24.com/login/x?autologin=clear"]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.click(
                _REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS,
                verify_target=lambda u: u == _REAL_URL, select_existing_target=False,
            )

    fake_session.event_bus.dispatch.assert_called_once()  # click did happen; the post-click read is what's blocked


def test_click_requires_verified_post_change_content_actually_polled():
    fake_session = _fake_session(_real_back_button_map())
    fake_session.get_state_as_text.side_effect = [_TEXT_BEFORE, _TEXT_BEFORE, _TEXT_AFTER, _TEXT_AFTER]
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = VerifiedButtonClickAdvancer()
        result = advancer.click(
            _REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS,
            content_changed=lambda t: t == _TEXT_AFTER, content_change_timeout=5.0, select_existing_target=False,
        )

    assert result.content_changed is True
    assert result.text_content == _TEXT_AFTER


def test_session_is_always_stopped_even_on_failure():
    fake_session = _fake_session(_real_back_button_map())
    fake_session.event_bus.dispatch.side_effect = RuntimeError("real dispatch failure")
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedButtonClickAdvancer()
        with pytest.raises(BrowserUseError):
            advancer.click(_REAL_URL, attributes_match=lambda a: a.get("class") == _BACK_CLASS, select_existing_target=False)

    fake_session.stop.assert_awaited_once()


def test_button_click_advancer_module_exposes_no_form_input_or_navigate_capability():
    import atlas.integrations.browser_button_click_advancer as module

    source = inspect.getsource(module)
    forbidden_code_patterns = (
        "Tools(", "from browser_use.tools", "import Tools", ".input_text(", ".upload_file(",
        ".send_keys(", ".navigate_to(", "TypeTextEvent", "SendKeysEvent", "UploadFileEvent",
        "NavigateToUrlEvent", "GoBackEvent", "BrowserHands", "browser_hands",
    )
    for forbidden in forbidden_code_patterns:
        assert forbidden not in source, f"{forbidden!r} must never appear as real code in VerifiedButtonClickAdvancer's module"
