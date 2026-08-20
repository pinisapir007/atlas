from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.integrations.browser_use_observer import BrowserUseError, BrowserUseObserver

# Real, observed values from a real, live call made before this test file
# was written (example.com, 2026-08-06) -- mirrors the exact
# "test against the real observed shape" discipline
# tests/integrations/test_claude_provider.py already established for its
# own real, live-observed response envelope.
_REAL_TITLE = "example.com"
_REAL_URL = "https://example.com/"
_REAL_TEXT = "Example Domain\nThis domain is for use in documentation examples without needing permission."


def _fake_session():
    session = AsyncMock()
    session.get_current_page_title.return_value = _REAL_TITLE
    session.get_current_page_url.return_value = _REAL_URL
    session.get_state_as_text.return_value = _REAL_TEXT
    return session


class _FakeTarget:
    """Stands in for a real browser_use Target -- only the two real
    fields _select_target_by_url() actually reads."""

    def __init__(self, url: str, target_id: str):
        self.url = url
        self.target_id = target_id


def test_observe_returns_the_real_navigated_content():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com")

    assert result.url == _REAL_URL
    assert result.title == _REAL_TITLE
    assert result.text_content == _REAL_TEXT
    assert result.structured_data == {}
    fake_session.navigate_to.assert_awaited_once_with("https://example.com")
    fake_session.start.assert_awaited_once()
    fake_session.stop.assert_awaited_once()


def test_cdp_url_is_passed_through_to_browser_session_when_provided():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session) as MockSession:
        observer = BrowserUseObserver(api_key="fake-key", cdp_url="http://localhost:9222")
        observer.observe("https://example.com")

    MockSession.assert_called_once_with(cdp_url="http://localhost:9222")


def test_existing_caller_without_cdp_url_gets_the_exact_original_behavior():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session) as MockSession:
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com")

    # None is BrowserSession's own real default too (confirmed by direct
    # inspection of the installed browser_use==0.13.7 signature) -- passing
    # it explicitly is not a behavior change from omitting it.
    MockSession.assert_called_once_with(cdp_url=None)
    assert result.url == _REAL_URL
    assert result.title == _REAL_TITLE
    assert result.text_content == _REAL_TEXT


def test_verify_target_rejects_before_text_or_screenshot_is_ever_read():
    # The real proof this test exists for: an unapproved real destination
    # must never have its content read at all -- not read then discarded
    # by a caller-side check afterward. take_screenshot() is stubbed to
    # return real-looking bytes specifically so a bug that captured it
    # anyway would be caught by the assert_not_called() below, not hidden
    # by an empty/falsy default.
    fake_session = _fake_session()
    fake_session.take_screenshot.return_value = b"should-never-be-captured"
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match="not within the approved target scope"):
            observer.observe("https://example.com", include_screenshot=True, verify_target=lambda real_url: False)

    fake_session.get_state_as_text.assert_not_called()
    fake_session.take_screenshot.assert_not_called()
    fake_session.navigate_to.assert_awaited_once()  # navigation itself must still happen -- that's how real_url is known
    fake_session.stop.assert_awaited_once()  # cleanup still runs even on this new failure path


def test_verify_target_allows_observation_through_when_it_returns_true():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com", verify_target=lambda real_url: True)

    assert result.text_content == _REAL_TEXT
    fake_session.get_state_as_text.assert_awaited_once()


def test_without_page_ready_check_behavior_is_completely_unchanged():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com")

    assert fake_session.get_state_as_text.await_count == 1  # exactly the original single read, no polling introduced
    assert result.text_content == _REAL_TEXT


def test_page_ready_check_returns_immediately_when_already_ready():
    fake_session = _fake_session()  # get_state_as_text always returns _REAL_TEXT
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com", page_ready_check=lambda text: True)

    # One call for the poll's own ready-check (True on the first try), one
    # more for the final read after the second verify -- never a sleep.
    assert fake_session.get_state_as_text.await_count == 2
    assert result.text_content == _REAL_TEXT


def test_page_ready_check_stops_exactly_when_condition_becomes_true():
    fake_session = _fake_session()
    # Three "still loading" reads, then ready, then one more for the final
    # read -- if the poll over-runs past finding "ready", the mock's
    # side_effect list is exhausted and the test fails loudly, not silently.
    fake_session.get_state_as_text.side_effect = ["loading...", "loading...", "loading...", _REAL_TEXT, _REAL_TEXT]
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe(
            "https://example.com",
            page_ready_check=lambda text: text == _REAL_TEXT,
            page_ready_timeout=5.0,
        )

    assert fake_session.get_state_as_text.await_count == 5
    assert result.text_content == _REAL_TEXT


def test_page_ready_check_times_out_with_a_bounded_clear_explanation():
    fake_session = _fake_session()  # real content is returned, but our condition never accepts it
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match=r"did not become ready within 0\.05s"):
            observer.observe("https://example.com", page_ready_check=lambda text: False, page_ready_timeout=0.05)


def test_target_change_during_the_wait_to_an_unapproved_domain_is_rejected_before_the_final_read():
    fake_session = _fake_session()
    # get_current_page_url resolves to the approved URL right after
    # navigation, then to a *different*, unapproved URL after the
    # readiness wait -- a real client-side redirect that happened during
    # the wait must be caught by the second, freshly re-resolved check.
    fake_session.get_current_page_url.side_effect = [_REAL_URL, "https://not-approved.example/redirected"]
    with patch("browser_use.BrowserSession", return_value=fake_session), patch("asyncio.sleep", new=AsyncMock()):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match="not within the approved target scope"):
            observer.observe(
                "https://example.com",
                verify_target=lambda u: u == _REAL_URL,
                page_ready_check=lambda text: True,  # ready immediately -- reach the second verify quickly
            )

    # get_state_as_text was called once for the readiness poll's own
    # check, but never again for a "final" read -- the second verify_target
    # rejected before that could ever happen.
    assert fake_session.get_state_as_text.await_count == 1


def test_skip_navigate_if_already_there_skips_navigation_on_exact_match():
    fake_session = _fake_session()  # get_current_page_url already returns _REAL_URL
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe(_REAL_URL, skip_navigate_if_already_there=True)

    fake_session.navigate_to.assert_not_called()
    assert result.url == _REAL_URL
    assert result.text_content == _REAL_TEXT


def test_skip_navigate_if_already_there_falls_back_to_navigate_on_mismatch():
    fake_session = _fake_session()  # get_current_page_url returns _REAL_URL -- different from the requested URL below
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        observer.observe("https://example.com/different-page", skip_navigate_if_already_there=True)

    fake_session.navigate_to.assert_awaited_once_with("https://example.com/different-page")


def test_without_skip_navigate_flag_navigation_always_happens_even_on_url_match():
    # The exact scenario where skipping *would* apply if the flag were set --
    # proves the default (False) preserves the exact original behavior, not
    # just "usually" preserves it.
    fake_session = _fake_session()  # get_current_page_url already equals _REAL_URL
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        observer.observe(_REAL_URL)  # skip_navigate_if_already_there defaults to False

    fake_session.navigate_to.assert_awaited_once_with(_REAL_URL)


def test_verify_target_still_applies_when_navigation_is_skipped():
    fake_session = _fake_session()  # get_current_page_url consistently returns _REAL_URL
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match="not within the approved target scope"):
            observer.observe(_REAL_URL, skip_navigate_if_already_there=True, verify_target=lambda u: False)

    fake_session.navigate_to.assert_not_called()  # confirms the skip path was really taken
    fake_session.get_state_as_text.assert_not_called()  # content still never read despite the skip


def test_page_ready_check_still_runs_when_navigation_is_skipped():
    fake_session = _fake_session()  # get_current_page_url matches -> navigation is skipped
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe(_REAL_URL, skip_navigate_if_already_there=True, page_ready_check=lambda text: True)

    fake_session.navigate_to.assert_not_called()
    assert result.text_content == _REAL_TEXT


def test_select_existing_target_focuses_the_single_matching_target():
    fake_session = _fake_session()
    fake_session.session_manager = MagicMock()
    fake_session.session_manager.get_all_page_targets.return_value = [
        _FakeTarget(url="https://other.example/", target_id="target-A"),
        _FakeTarget(url=_REAL_URL, target_id="target-B"),
    ]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe(_REAL_URL, select_existing_target=True)

    fake_session.get_or_create_cdp_session.assert_awaited_once_with("target-B", focus=True)
    assert result.text_content == _REAL_TEXT


def test_select_existing_target_fails_closed_when_no_target_matches():
    fake_session = _fake_session()
    fake_session.session_manager = MagicMock()
    fake_session.session_manager.get_all_page_targets.return_value = [
        _FakeTarget(url="https://other.example/", target_id="target-A"),
    ]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match="no existing browser target"):
            observer.observe(_REAL_URL, select_existing_target=True)

    fake_session.get_or_create_cdp_session.assert_not_called()  # never a fallback guess


def test_select_existing_target_fails_closed_on_ambiguous_match():
    fake_session = _fake_session()
    fake_session.session_manager = MagicMock()
    fake_session.session_manager.get_all_page_targets.return_value = [
        _FakeTarget(url=_REAL_URL, target_id="target-A"),
        _FakeTarget(url=_REAL_URL, target_id="target-B"),
    ]
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match="ambiguous"):
            observer.observe(_REAL_URL, select_existing_target=True)

    fake_session.get_or_create_cdp_session.assert_not_called()  # never picks the first one as a guess


def test_without_select_existing_target_behavior_is_unchanged():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe(_REAL_URL)  # select_existing_target defaults to False

    fake_session.get_or_create_cdp_session.assert_not_called()  # the new code path is never even entered
    assert result.text_content == _REAL_TEXT


def test_session_is_stopped_even_if_navigation_fails():
    fake_session = _fake_session()
    fake_session.navigate_to.side_effect = RuntimeError("net::ERR_NAME_NOT_RESOLVED")
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        with pytest.raises(BrowserUseError, match="ERR_NAME_NOT_RESOLVED"):
            observer.observe("https://does-not-exist.example")

    fake_session.stop.assert_awaited_once()  # cleanup still happens on a real failure


def test_extract_without_an_api_key_raises_clearly(monkeypatch):
    # This machine has a real GEMINI_API_KEY set persistently -- must be
    # explicitly cleared for this test to genuinely exercise "no key",
    # not just rely on api_key=None (which would silently fall back to
    # the real env var and defeat the test's own premise).
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key=None)
        with pytest.raises(BrowserUseError, match="GEMINI_API_KEY"):
            observer.observe("https://example.com", extract={"heading": "the heading"})


def test_extract_uses_structured_output_and_returns_real_fields():
    fake_session = _fake_session()
    fake_completion = AsyncMock()
    fake_response = type("R", (), {"completion": type("M", (), {"model_dump": lambda self: {"heading": "Example Domain"}})()})()

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com", extract={"heading": "the main heading"})

    assert result.structured_data == {"heading": "Example Domain"}
    MockChatGoogle.assert_called_once()
    _, call_kwargs = MockChatGoogle.call_args
    assert call_kwargs["api_key"] == "fake-key"


def test_default_api_key_comes_from_the_real_gemini_api_key_env_var(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-123")
    observer = BrowserUseObserver()
    assert observer._api_key == "env-key-123"


def test_explicit_api_key_overrides_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-123")
    observer = BrowserUseObserver(api_key="explicit-key")
    assert observer._api_key == "explicit-key"


def test_a_real_injected_ai_provider_is_used_instead_of_gemini_with_zero_code_changes():
    # The actual claim behind the AI Orchestrator (2026-08-06): the AI
    # backend can be swapped by passing a different real AIProvider,
    # with zero changes to this module's own code. Proven here with a
    # fake provider standing in for a real one (e.g. ClaudeProvider) --
    # the point is that BrowserUseObserver never constructs ChatGoogle
    # at all when a provider is injected.
    fake_session = _fake_session()

    class _FakeProvider:
        name = "fake"

        def __init__(self):
            self.calls = []

        def complete(self, prompt):
            raise AssertionError("complete() should not be called for structured extraction")

        def complete_structured(self, prompt, fields):
            self.calls.append((prompt, fields))
            return {key: f"real-{key}-value" for key in fields}

    fake_provider = _FakeProvider()
    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        observer = BrowserUseObserver(api_key="unused", ai_provider=fake_provider)
        result = observer.observe("https://example.com", extract={"heading": "the main heading"})

    assert result.structured_data == {"heading": "real-heading-value"}
    assert len(fake_provider.calls) == 1
    MockChatGoogle.assert_not_called()  # the real Gemini backend was never touched


def test_a_real_provider_failure_during_extraction_is_wrapped_as_browser_use_error():
    fake_session = _fake_session()

    class _FailingProvider:
        name = "failing"

        def complete_structured(self, prompt, fields):
            raise RuntimeError("real provider outage")

    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="unused", ai_provider=_FailingProvider())
        with pytest.raises(BrowserUseError, match="real provider outage"):
            observer.observe("https://example.com", extract={"heading": "the heading"})


def test_without_include_screenshot_no_screenshot_is_taken_or_saved():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com")

    fake_session.take_screenshot.assert_not_called()
    assert result.screenshot_path == ""


def test_include_screenshot_captures_saves_and_understands_a_real_screenshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_session = _fake_session()
    fake_session.take_screenshot.return_value = b"real-fake-screenshot-png-bytes"
    fake_response = type("R", (), {"completion": "A real page showing example.com."})()

    with patch("browser_use.BrowserSession", return_value=fake_session), \
         patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com", include_screenshot=True)

    fake_session.take_screenshot.assert_awaited_once()
    assert result.screenshot_path != ""
    from pathlib import Path
    assert Path(result.screenshot_path).read_bytes() == b"real-fake-screenshot-png-bytes"
    assert result.structured_data["screenshot_description"] == "A real page showing example.com."


def test_include_screenshot_false_by_default_preserves_exact_original_behavior():
    fake_session = _fake_session()
    with patch("browser_use.BrowserSession", return_value=fake_session):
        observer = BrowserUseObserver(api_key="fake-key")
        result = observer.observe("https://example.com")

    assert result.url == _REAL_URL
    assert result.title == _REAL_TITLE
    assert result.text_content == _REAL_TEXT
    assert result.structured_data == {}
