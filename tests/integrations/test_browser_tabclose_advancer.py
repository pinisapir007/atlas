import inspect
import itertools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.integrations.browser_tabclose_advancer import (
    ExpectedTargetMissingError,
    TargetNotFoundError,
    VerifiedTabCloseAdvancer,
)

MARKETPLACE_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
MARKETPLACE_TARGET_ID = "marketplace-target-1"
SALES_PAGE_TARGET_ID = "sales-page-target-2"


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


def _fake_session(targets_before, targets_after):
    """First call (the pre-dispatch check) returns `targets_before`;
    every call after that (the poll loop) returns `targets_after` --
    matches the real, one-directional state transition a real close
    produces (never flips back), while letting the poll loop call
    get_all_page_targets() an unbounded number of times without
    exhausting a fixed side_effect list."""
    session = AsyncMock()
    session.session_manager = MagicMock()
    session.session_manager.get_all_page_targets.side_effect = itertools.chain([targets_before], itertools.repeat(targets_after))
    session.event_bus = MagicMock()
    session.event_bus.dispatch.return_value = _FakeEvent()
    return session


def test_close_dispatches_exactly_one_closetab_event_for_the_right_target():
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID), _FakeTarget("https://external.example/", SALES_PAGE_TARGET_ID)]
    after = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID)]
    fake_session = _fake_session(before, after)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedTabCloseAdvancer(cdp_url="http://localhost:9222")
        result = advancer.close(SALES_PAGE_TARGET_ID, expected_remaining_url=MARKETPLACE_URL)

    fake_session.event_bus.dispatch.assert_called_once()
    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert type(dispatched_event).__name__ == "CloseTabEvent"
    assert dispatched_event.target_id == SALES_PAGE_TARGET_ID
    assert result.closed_target_id == SALES_PAGE_TARGET_ID
    assert result.remaining_urls == [MARKETPLACE_URL]


def test_close_fails_closed_when_target_id_not_currently_open():
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID)]
    fake_session = _fake_session(before, before)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedTabCloseAdvancer()
        with pytest.raises(TargetNotFoundError):
            advancer.close("nonexistent-target", expected_remaining_url=MARKETPLACE_URL)

    fake_session.event_bus.dispatch.assert_not_called()


def test_close_fails_closed_when_expected_remaining_url_not_found_after_close():
    """The exact, narrow gate this class exists for: a technically-
    successful close is never trusted alone as proof the original
    context survived."""
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID), _FakeTarget("https://external.example/", SALES_PAGE_TARGET_ID)]
    after = [_FakeTarget("https://www.digistore24.com/login/x?autologin=clear", MARKETPLACE_TARGET_ID)]
    fake_session = _fake_session(before, after)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedTabCloseAdvancer()
        with pytest.raises(ExpectedTargetMissingError):
            advancer.close(SALES_PAGE_TARGET_ID, expected_remaining_url=MARKETPLACE_URL)


def test_close_fails_when_closed_target_still_present_afterward():
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID), _FakeTarget("https://external.example/", SALES_PAGE_TARGET_ID)]
    after = list(before)  # close "succeeded" but target is still there
    fake_session = _fake_session(before, after)
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        advancer = VerifiedTabCloseAdvancer()
        with pytest.raises(RuntimeError, match="still present"):
            advancer.close(SALES_PAGE_TARGET_ID, expected_remaining_url=MARKETPLACE_URL, poll_timeout=0.01)


def test_session_is_always_stopped_even_on_failure():
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID), _FakeTarget("https://external.example/", SALES_PAGE_TARGET_ID)]
    fake_session = _fake_session(before, before)
    fake_session.event_bus.dispatch.side_effect = RuntimeError("real dispatch failure")
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedTabCloseAdvancer()
        with pytest.raises(RuntimeError):
            advancer.close(SALES_PAGE_TARGET_ID, expected_remaining_url=MARKETPLACE_URL)

    fake_session.stop.assert_awaited_once()


def test_close_polls_when_target_list_has_not_yet_updated():
    """Real, live-confirmed timing gap (2026-08-17): the real close can
    succeed before session_manager's own internal target list has
    processed it -- this proves the bounded poll actually retries
    rather than trusting a single, possibly-stale read."""
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID), _FakeTarget("https://external.example/", SALES_PAGE_TARGET_ID)]
    still_present = list(before)
    now_closed = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID)]

    session = AsyncMock()
    session.session_manager = MagicMock()
    # pre-dispatch check, then one stale poll read, then the real, updated read
    session.session_manager.get_all_page_targets.side_effect = [before, still_present, now_closed]
    session.event_bus = MagicMock()
    session.event_bus.dispatch.return_value = _FakeEvent()

    with patch("browser_use.BrowserSession", return_value=session), patch("asyncio.sleep", new=AsyncMock()) as fake_sleep:
        advancer = VerifiedTabCloseAdvancer()
        result = advancer.close(SALES_PAGE_TARGET_ID, expected_remaining_url=MARKETPLACE_URL)

    assert result.remaining_urls == [MARKETPLACE_URL]
    fake_sleep.assert_awaited()  # a real poll wait genuinely happened, not a lucky single read


def test_never_closes_a_different_target_than_requested():
    """Structural proof: only the exact requested target_id is ever
    passed to CloseTabEvent, never inferred/guessed from context."""
    before = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID), _FakeTarget("https://external.example/", SALES_PAGE_TARGET_ID)]
    after = [_FakeTarget(MARKETPLACE_URL, MARKETPLACE_TARGET_ID)]
    fake_session = _fake_session(before, after)
    with patch("browser_use.BrowserSession", return_value=fake_session):
        advancer = VerifiedTabCloseAdvancer()
        advancer.close(SALES_PAGE_TARGET_ID, expected_remaining_url=MARKETPLACE_URL)

    dispatched_event = fake_session.event_bus.dispatch.call_args[0][0]
    assert dispatched_event.target_id != MARKETPLACE_TARGET_ID


def test_tabclose_advancer_module_exposes_no_form_input_click_or_navigate_capability():
    import atlas.integrations.browser_tabclose_advancer as module

    source = inspect.getsource(module)
    forbidden_code_patterns = (
        "Tools(", "from browser_use.tools", "import Tools", ".input_text(", ".upload_file(",
        ".send_keys(", ".navigate_to(", "ClickElementEvent", "GoBackEvent", "TypeTextEvent",
        "SendKeysEvent", "UploadFileEvent", "NavigateToUrlEvent", "BrowserHands", "browser_hands",
    )
    for forbidden in forbidden_code_patterns:
        assert forbidden not in source, f"{forbidden!r} must never appear as real code in VerifiedTabCloseAdvancer's module"
