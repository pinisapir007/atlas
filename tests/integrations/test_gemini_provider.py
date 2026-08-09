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


def test_complete_omits_max_output_tokens_by_default_preserving_chatgoogles_own_default():
    # Real bug, found live (2026-08-09): a real, large delegated task
    # (a complete self-contained HTML design mockup) silently truncated
    # mid-file because ChatGoogle's own max_output_tokens=8096 default
    # was never overridden. Every existing caller must keep getting
    # ChatGoogle's own default unchanged -- this provider must never
    # pass an explicit max_output_tokens unless the caller asked for one.
    fake_response = type("R", (), {"completion": "PONG"})()
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        GeminiProvider(api_key="fake-key").complete("ping")

    _, call_kwargs = MockChatGoogle.call_args
    assert "max_output_tokens" not in call_kwargs


def test_complete_passes_a_real_explicit_max_output_tokens_override():
    fake_response = type("R", (), {"completion": "a very long real response"})()
    with patch("browser_use.llm.google.chat.ChatGoogle") as MockChatGoogle:
        MockChatGoogle.return_value.ainvoke = AsyncMock(return_value=fake_response)
        GeminiProvider(api_key="fake-key", max_output_tokens=32000).complete("write a long real document")

    _, call_kwargs = MockChatGoogle.call_args
    assert call_kwargs["max_output_tokens"] == 32000


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


def _fake_genai_client(text_response=None, json_response=None):
    """Builds a fake google.genai.Client whose aio.models.generate_content
    returns a real-shaped response object (a .text attribute), mirroring
    how the real SDK's response is used by every audio/video/youtube
    method under test here."""
    client = AsyncMock()
    fake_response = type("R", (), {"text": json_response if json_response is not None else text_response})()
    client.aio.models.generate_content = AsyncMock(return_value=fake_response)
    return client


def test_understand_audio_returns_the_real_text_response():
    fake_client = _fake_genai_client(text_response="Atlas hearing test. The keto diet product costs $47.")
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_audio(b"fake-wav-bytes", "Transcribe this audio verbatim.")

    assert result == "Atlas hearing test. The keto diet product costs $47."


def test_understand_audio_without_an_api_key_raises_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY"):
        provider.understand_audio(b"fake-bytes", "transcribe this")


def test_understand_audio_structured_parses_real_json_response():
    fake_client = _fake_genai_client(json_response='{"price": "$47"}')
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_audio_structured(b"fake-bytes", "extract the price", {"price": "the price mentioned"})

    assert result == {"price": "$47"}


def test_understand_audio_wraps_a_real_failure_loudly():
    fake_client = AsyncMock()
    fake_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("real audio quota exceeded"))
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(GeminiProviderError, match="real audio quota exceeded"):
            provider.understand_audio(b"fake-bytes", "transcribe this")


def test_understand_video_returns_the_real_text_response():
    fake_client = _fake_genai_client(text_response="A real video showing a product demo.")
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_video(b"fake-mp4-bytes", "describe this video")

    assert result == "A real video showing a product demo."


def test_understand_video_without_an_api_key_raises_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY"):
        provider.understand_video(b"fake-bytes", "describe this")


def test_understand_video_structured_parses_real_json_response():
    fake_client = _fake_genai_client(json_response='{"product": "KetoDNA"}')
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_video_structured(b"fake-bytes", "look at this", {"product": "the product shown"})

    assert result == {"product": "KetoDNA"}


def test_understand_video_wraps_a_real_failure_loudly():
    fake_client = AsyncMock()
    fake_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("real video quota exceeded"))
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(GeminiProviderError, match="real video quota exceeded"):
            provider.understand_video(b"fake-bytes", "describe this")


def test_understand_youtube_returns_the_real_text_response():
    fake_client = _fake_genai_client(text_response="Jawed Karim at the San Diego Zoo elephant enclosure.")
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_youtube("https://www.youtube.com/watch?v=jNQXAC9IVRw", "what is shown?")

    assert result == "Jawed Karim at the San Diego Zoo elephant enclosure."
    call_args, call_kwargs = fake_client.aio.models.generate_content.call_args
    parts = call_kwargs["contents"]
    assert parts[0].file_data.file_uri == "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def test_understand_youtube_without_an_api_key_raises_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY"):
        provider.understand_youtube("https://www.youtube.com/watch?v=abc", "describe this")


def test_understand_youtube_structured_parses_real_json_response():
    fake_client = _fake_genai_client(json_response='{"topic": "elephants"}')
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        result = provider.understand_youtube_structured(
            "https://www.youtube.com/watch?v=abc", "watch this", {"topic": "the main topic"}
        )

    assert result == {"topic": "elephants"}


def test_understand_youtube_wraps_a_real_failure_loudly():
    fake_client = AsyncMock()
    fake_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("real youtube quota exceeded"))
    with patch("google.genai.Client", return_value=fake_client):
        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(GeminiProviderError, match="real youtube quota exceeded"):
            provider.understand_youtube("https://www.youtube.com/watch?v=abc", "describe this")
