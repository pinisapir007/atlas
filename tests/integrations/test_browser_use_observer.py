from unittest.mock import AsyncMock, patch

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
