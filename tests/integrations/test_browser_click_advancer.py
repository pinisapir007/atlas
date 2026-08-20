import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from browser_use.dom.views import EnhancedDOMTreeNode, NodeType

from atlas.integrations.browser_click_advancer import VerifiedClickAdvancer
from atlas.integrations.browser_use_observer import BrowserUseError

_REAL_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
_PAGE_2_HREF = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all?page=2"
_TEXT_BEFORE = "page 1 content"
_TEXT_AFTER = "page 2 content, changed"


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


def _FakeNode(tag_name: str, href: str | None = None, extra_attrs: dict | None = None) -> EnhancedDOMTreeNode:
    """A real, minimal EnhancedDOMTreeNode -- ClickElementEvent's own
    field_validator reconstructs a node from real dataclass fields
    (node_id, backend_node_id, node_type, node_name, attributes, ...), so
    a hand-rolled fake object can never satisfy it; this constructs the
    real type with the smallest valid field set instead."""
    attrs = dict(extra_attrs or {})
    if href is not None:
        attrs["href"] = href
    node_id = _next_node_id[0]
    _next_node_id[0] += 1
    return EnhancedDOMTreeNode(
        node_id=node_id,
        backend_node_id=node_id,
        node_type=NodeType.ELEMENT_NODE,
        node_name=tag_name.upper(),
        node_value="",
        attributes=attrs,
        is_scrollable=None,
        is_visible=True,
        absolute_position=None,
        target_id="target-1",
        frame_id=None,
        session_id=None,
        content_document=None,
        shadow_root_type=None,
        shadow_roots=None,
        parent_node=None,
        children_nodes=None,
        ax_node=None,
        snapshot_node=None,
    )


def _fake_session(selector_map: dict):
    session = AsyncMock()
    session.get_current_page_url.return_value = _REAL_URL
    session.get_state_as_text.return_value = _TEXT_BEFORE
    session.session_manager = MagicMock()
    session.session_manager.get_all_page_targets.return_value = [_FakeTarget(url=_REAL_URL, target_id="target-1")]
    session.event_bus = MagicMock()
    session.event_bus.dispatch.return_value = _FakeEvent()
    fake_summary = MagicMock()
    fake_summary.dom_state.selector_map = selector_map
    session.get_browser_state_summary = AsyncMock(return_value=fake_summary)
    return session


def _single_page_2_link_map():
    return {
        1: _FakeNode("a", href="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all?page=1"),
        2: _FakeNode("a", href=_PAGE_2_HREF),
        3: _FakeNode("div", href=_PAGE_2_HREF),  # not an <a>, must never count
    }


def test_click_dispatches_exactly_one_click_event_on_the_matched_node():
    fake_session = _fake_session(_single_page_2_link_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer(cdp_url="http://localhost:9222")
        result = advancer.click(_REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_called_once()
    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert type(dispatched_event).__name__ == "ClickElementEvent"
    assert result.clicked_href == _PAGE_2_HREF


def test_click_selects_the_existing_target_before_clicking():
    fake_session = _fake_session(_single_page_2_link_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        VerifiedClickAdvancer().click(_REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, select_existing_target=True)

    fake_session.get_or_create_cdp_session.assert_awaited_once_with("target-1", focus=True)


def test_click_fails_closed_with_zero_matching_hrefs():
    fake_session = _fake_session(_single_page_2_link_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        with pytest.raises(BrowserUseError, match="0 matches"):
            advancer.click(_REAL_URL, href_matches=lambda h: h == "https://no-such-page.example", select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_fails_closed_with_more_than_one_distinct_matching_href():
    selector_map = {
        1: _FakeNode("a", href="https://example.com/x"),
        2: _FakeNode("a", href="https://example.com/y"),
    }
    fake_session = _fake_session(selector_map)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        with pytest.raises(BrowserUseError, match="[Aa]mbiguous"):
            advancer.click(_REAL_URL, href_matches=lambda h: h.startswith("https://example.com"), select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_succeeds_when_multiple_nodes_share_the_identical_real_href():
    """Duplicate <a> nodes pointing at the exact same real href are not
    ambiguous -- proven live during the Page 1->2 transition."""
    selector_map = {
        1: _FakeNode("a", href=_PAGE_2_HREF),
        2: _FakeNode("a", href=_PAGE_2_HREF),  # identical href, different node
    }
    fake_session = _fake_session(selector_map)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        result = advancer.click(_REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_called_once()
    assert result.clicked_href == _PAGE_2_HREF


def test_click_fails_closed_when_target_mismatches_before_clicking():
    fake_session = _fake_session(_single_page_2_link_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.click(_REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, verify_target=lambda u: False, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_click_fails_closed_when_target_changes_after_clicking():
    fake_session = _fake_session(_single_page_2_link_map())
    fake_session.get_current_page_url.side_effect = [_REAL_URL, "https://not-approved.example/redirected"]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.click(
                _REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, verify_target=lambda u: u == _REAL_URL, select_existing_target=False
            )

    fake_session.event_bus.dispatch.assert_called_once()  # click did happen; the post-click read is what's blocked


def test_click_requires_verified_post_change_content_actually_polled():
    fake_session = _fake_session(_single_page_2_link_map())
    fake_session.get_state_as_text.side_effect = [_TEXT_BEFORE, _TEXT_BEFORE, _TEXT_AFTER, _TEXT_AFTER]
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = VerifiedClickAdvancer()
        result = advancer.click(
            _REAL_URL,
            href_matches=lambda h: h == _PAGE_2_HREF,
            content_changed=lambda t: t == _TEXT_AFTER,
            content_change_timeout=5.0,
            select_existing_target=False,
        )

    assert result.content_changed is True
    assert result.text_content == _TEXT_AFTER


def test_click_never_dispatched_when_target_verification_fails_first():
    """Fire-and-forget is never acceptable: rejection happens before any
    real click action."""
    fake_session = _fake_session(_single_page_2_link_map())
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        with pytest.raises(BrowserUseError):
            advancer.click(_REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, verify_target=lambda u: False, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()


def test_session_is_always_stopped_even_on_failure():
    fake_session = _fake_session(_single_page_2_link_map())
    fake_session.event_bus.dispatch.side_effect = RuntimeError("real dispatch failure")
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedClickAdvancer()
        with pytest.raises(BrowserUseError):
            advancer.click(_REAL_URL, href_matches=lambda h: h == _PAGE_2_HREF, select_existing_target=False)

    fake_session.stop.assert_awaited_once()


def test_click_advancer_module_exposes_no_form_input_or_navigate_capability():
    """Structural, same discipline as DiscoveryScrollAdvancer's own test:
    this module must never be able to do anything except click+read."""
    import atlas.integrations.browser_click_advancer as module

    source = inspect.getsource(module)
    forbidden_code_patterns = (
        "Tools(",
        "from browser_use.tools",
        "import Tools",
        ".input_text(",
        ".upload_file(",
        ".send_keys(",
        ".navigate_to(",
        "TypeTextEvent",
        "SendKeysEvent",
        "UploadFileEvent",
        "NavigateToUrlEvent",
        "BrowserHands",
        "browser_hands",
    )
    for forbidden in forbidden_code_patterns:
        assert forbidden not in source, f"{forbidden!r} must never appear as real code in VerifiedClickAdvancer's module"
