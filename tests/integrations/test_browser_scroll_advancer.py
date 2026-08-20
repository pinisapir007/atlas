import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.integrations.browser_scroll_advancer import DiscoveryScrollAdvancer, scroll_pages_above, scroll_pages_below
from atlas.integrations.browser_use_observer import BrowserUseError

_REAL_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
_TEXT_BEFORE = "before-scroll content"
_TEXT_AFTER = "after-scroll content, changed"


class _FakeEvent:
    """Stands in for browser_use's real event-bus dispatch return value:
    directly awaitable, and separately exposes an async event_result()."""

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


def _fake_session():
    session = AsyncMock()
    session.get_current_page_url.return_value = _REAL_URL
    session.get_state_as_text.return_value = _TEXT_BEFORE
    session.session_manager = MagicMock()
    session.session_manager.get_all_page_targets.return_value = [_FakeTarget(url=_REAL_URL, target_id="target-1")]
    session.event_bus = MagicMock()
    session.event_bus.dispatch.return_value = _FakeEvent()
    return session


def test_advance_dispatches_exactly_one_scroll_event():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer(cdp_url="http://localhost:9222")
        result = advancer.advance(_REAL_URL)

    fake_session.event_bus.dispatch.assert_called_once()
    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert type(dispatched_event).__name__ == "ScrollEvent"
    assert dispatched_event.direction == "down"
    assert result.text_content == _TEXT_BEFORE
    assert result.content_changed is False  # no content_changed predicate given


def test_advance_selects_the_existing_target_before_scrolling():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer()
        advancer.advance(_REAL_URL, select_existing_target=True)

    fake_session.get_or_create_cdp_session.assert_awaited_once_with("target-1", focus=True)


def test_advance_fails_closed_when_target_does_not_match_before_scroll():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.advance(_REAL_URL, verify_target=lambda u: False, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_not_called()  # rejected before the scroll ever happens


def test_advance_fails_closed_when_target_changes_after_scroll():
    fake_session = _fake_session()
    fake_session.get_current_page_url.side_effect = [_REAL_URL, "https://not-approved.example/redirected"]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.advance(_REAL_URL, verify_target=lambda u: u == _REAL_URL, select_existing_target=False)

    fake_session.event_bus.dispatch.assert_called_once()  # the scroll itself did happen; the *read* is what's blocked


def test_content_changed_poll_stops_exactly_when_condition_becomes_true():
    fake_session = _fake_session()
    fake_session.get_state_as_text.side_effect = [_TEXT_BEFORE, _TEXT_BEFORE, _TEXT_AFTER, _TEXT_AFTER]
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = DiscoveryScrollAdvancer()
        result = advancer.advance(
            _REAL_URL, content_changed=lambda t: t == _TEXT_AFTER, content_change_timeout=5.0, select_existing_target=False
        )

    assert result.content_changed is True
    assert result.text_content == _TEXT_AFTER


def test_content_changed_poll_returns_false_on_timeout_without_raising():
    """A timeout here is a legitimate outcome (e.g. reached the end of the
    list), never an exception -- unlike BrowserUseObserver's page-ready
    wait, where "not ready" is always a real failure."""
    fake_session = _fake_session()
    fake_session.get_state_as_text.return_value = _TEXT_BEFORE  # never satisfies the predicate
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = DiscoveryScrollAdvancer()
        result = advancer.advance(
            _REAL_URL, content_changed=lambda t: False, content_change_timeout=0.05, select_existing_target=False
        )

    assert result.content_changed is False
    assert result.text_content == _TEXT_BEFORE


def test_real_url_after_scroll_is_freshly_re_resolved_not_reused():
    fake_session = _fake_session()
    fake_session.get_current_page_url.side_effect = [_REAL_URL, _REAL_URL]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer()
        result = advancer.advance(_REAL_URL, verify_target=lambda u: u == _REAL_URL, select_existing_target=False)

    assert fake_session.get_current_page_url.await_count == 2
    assert result.url == _REAL_URL


def test_session_is_always_stopped_even_on_failure():
    fake_session = _fake_session()
    fake_session.event_bus.dispatch.side_effect = RuntimeError("real dispatch failure")
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer()
        with pytest.raises(BrowserUseError):
            advancer.advance(_REAL_URL, select_existing_target=False)

    fake_session.stop.assert_awaited_once()


# --- Bidirectional scroll (2026-08-15, Digital Body Foundation) -----------


def test_advance_defaults_to_down_direction_backward_compatible():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        DiscoveryScrollAdvancer().advance(_REAL_URL)

    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert dispatched_event.direction == "down"


def test_advance_direction_up_dispatches_a_real_up_scroll_event():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        DiscoveryScrollAdvancer().advance(_REAL_URL, direction="up")

    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert dispatched_event.direction == "up"


def test_advance_rejects_an_invalid_direction_before_any_browser_session_starts():
    with patch("browser_use.BrowserSession") as session_cls:
        with pytest.raises(ValueError, match="direction"):
            DiscoveryScrollAdvancer().advance(_REAL_URL, direction="sideways")

    session_cls.assert_not_called()  # fail-fast: no session, no wasted real action


def test_advance_direction_up_still_fails_closed_on_target_mismatch_after_scroll():
    fake_session = _fake_session()
    fake_session.get_current_page_url.side_effect = [_REAL_URL, "https://not-approved.example/redirected"]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = DiscoveryScrollAdvancer()
        with pytest.raises(BrowserUseError, match="not within the approved scope"):
            advancer.advance(
                _REAL_URL, verify_target=lambda u: u == _REAL_URL, select_existing_target=False, direction="up"
            )

    fake_session.event_bus.dispatch.assert_called_once()  # the up-scroll itself did happen; the redirect check is what blocks


def test_advance_include_dom_captures_selector_map_in_the_same_session_moment():
    fake_session = _fake_session()
    fake_selector_map = {1: MagicMock(tag_name="a")}
    fake_summary = MagicMock()
    fake_summary.dom_state.selector_map = fake_selector_map
    fake_session.get_browser_state_summary = AsyncMock(return_value=fake_summary)

    with patch("browser_use.BrowserSession", return_value=fake_session):
        result = DiscoveryScrollAdvancer().advance(_REAL_URL, include_dom=True, select_existing_target=False)

    assert result.selector_map is fake_selector_map


def test_advance_without_include_dom_never_fetches_the_browser_state_summary():
    fake_session = _fake_session()
    fake_session.get_browser_state_summary = AsyncMock()

    with patch("browser_use.BrowserSession", return_value=fake_session):
        result = DiscoveryScrollAdvancer().advance(_REAL_URL, select_existing_target=False)

    fake_session.get_browser_state_summary.assert_not_called()
    assert result.selector_map is None
    assert result.dom_root is None


def test_advance_include_dom_also_captures_dom_root_in_the_same_session_moment():
    """Blocker 2 root-cause fix (2026-08-16): selector_map was live-proven
    to omit real tooltip-bearing nodes that the full dom tree (_root)
    reliably contains -- dom_root must be captured from the exact same
    get_browser_state_summary() call as selector_map, never a second,
    later read."""
    fake_session = _fake_session()
    fake_selector_map = {1: MagicMock(tag_name="a")}
    fake_root = MagicMock()
    fake_summary = MagicMock()
    fake_summary.dom_state.selector_map = fake_selector_map
    fake_summary.dom_state._root = fake_root
    fake_session.get_browser_state_summary = AsyncMock(return_value=fake_summary)

    with patch("browser_use.BrowserSession", return_value=fake_session):
        result = DiscoveryScrollAdvancer().advance(_REAL_URL, include_dom=True, select_existing_target=False)

    assert result.selector_map is fake_selector_map
    assert result.dom_root is fake_root
    fake_session.get_browser_state_summary.assert_awaited_once()  # one call captures both -- no second round-trip


# --- Orientation: scroll_pages_above/below ---------------------------------


def test_scroll_pages_above_reads_the_real_browser_use_annotation():
    text = "|scroll element|<mat-sidenav-content /> (2.5 pages above, 0.0 pages below)"
    assert scroll_pages_above(text) == 2.5
    assert scroll_pages_below(text) == 0.0


def test_scroll_pages_above_is_none_when_the_line_is_absent():
    assert scroll_pages_above("no scroll annotation here at all") is None


def test_scroll_pages_above_zero_is_a_real_reading_not_none():
    text = "(0.0 pages above, 3.0 pages below)"
    assert scroll_pages_above(text) == 0.0  # genuinely at the top, distinct from "unmeasured"


def test_advancer_module_exposes_no_click_input_submit_or_navigate_capability():
    """Structural, not just conventional: DiscoveryScrollAdvancer must
    never be able to do anything except scroll+read. Same discipline
    test_m1_marketplace_discovery_safety_wiring.py already established
    for BrowserUseObserver."""
    import atlas.integrations.browser_scroll_advancer as module

    source = inspect.getsource(module)
    forbidden_code_patterns = (
        "Tools(",
        "from browser_use.tools",
        "import Tools",
        ".click(",
        ".input_text(",
        ".upload_file(",
        ".send_keys(",
        ".navigate_to(",
        "BrowserHands",
        "browser_hands",
    )
    for forbidden in forbidden_code_patterns:
        assert forbidden not in source, f"{forbidden!r} must never appear as real code in DiscoveryScrollAdvancer's module"
