from unittest.mock import AsyncMock, patch

import pytest

from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError


def test_complete_returns_the_real_plain_text_response():
    fake_response = type("R", (), {"completion": "PONG"})()
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        provider = GeminiProvider(api_key="fake-key")
        result = provider.complete("Reply with exactly the single word: PONG")

    assert result == "PONG"
    _, call_kwargs = MockChatGoogle.call_args
    assert call_kwargs["api_key"] == "fake-key"


def test_complete_without_an_api_key_raises_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY"):
        provider.complete("a real prompt")


def test_complete_structured_uses_native_output_format_and_returns_real_fields():
    fake_response = type("R", (), {"completion": type("M", (), {"model_dump": lambda self: {"heading": "Example Domain"}})()})()
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        provider = GeminiProvider(api_key="fake-key")
        result = provider.complete_structured("extract the heading", {"heading": "the main heading"})

    assert result == {"heading": "Example Domain"}


def test_complete_structured_without_an_api_key_raises_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY"):
        provider.complete_structured("a real prompt", {"heading": "the heading"})


def test_default_api_key_comes_from_the_real_gemini_api_key_env_var(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-123")
    provider = GeminiProvider()
    assert provider._api_key == "env-key-123"


def test_a_real_chatgoogle_failure_is_wrapped_loudly():
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("real quota exceeded"))
        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(GeminiProviderError, match="real quota exceeded"):
            provider.complete("a real prompt")


def test_name_is_gemini():
    assert GeminiProvider().name == "gemini"


def test_understand_image_returns_the_real_text_response():
    fake_response = type("R", (), {"completion": "ATLAS VISION TEST 2026"})()
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_image(b"fake-png-bytes", "What text do you see?")

    assert result == "ATLAS VISION TEST 2026"
    call_args, call_kwargs = MockChatGoogle.return_value.ainvoke.call_args
    messages = call_args[0]
    # real, structured content: one text part, one real image part -- not a bare string
    assert len(messages[0].content) == 2


def test_understand_image_without_an_api_key_raises_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY"):
        provider.understand_image(b"fake-bytes", "describe this")


def test_understand_image_structured_uses_native_output_format():
    fake_response = type("R", (), {"completion": type("M", (), {"model_dump": lambda self: {"product": "KetoDNA"}})()})()
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_image_structured(b"fake-bytes", "look at this", {"product": "the product name"})

    assert result == {"product": "KetoDNA"}


def test_understand_image_wraps_a_real_failure_loudly():
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("real vision quota exceeded"))
        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(GeminiProviderError, match="real vision quota exceeded"):
            provider.understand_image(b"fake-bytes", "describe this")
