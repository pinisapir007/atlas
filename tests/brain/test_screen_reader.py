from unittest.mock import MagicMock, patch

import pytest

from atlas.brain.screen_reader import ScreenReader, ScreenReaderError


class _FakeGeminiProvider:
    name = "fake"

    def __init__(self, description="a real screen description"):
        self._description = description
        self.calls = []

    def understand_image(self, image_bytes, prompt, media_type="image/png"):
        self.calls.append((image_bytes, prompt, media_type))
        return self._description


def _fake_pil_image():
    """A minimal fake PIL Image whose .save() writes real, recognizable bytes."""
    fake = MagicMock()

    def _save(buf, format="PNG"):
        buf.write(b"real-fake-screen-png-bytes")

    fake.save.side_effect = _save
    return fake


def test_capture_returns_real_png_bytes():
    with patch("PIL.ImageGrab.grab", return_value=_fake_pil_image()):
        reader = ScreenReader(gemini_provider=_FakeGeminiProvider())
        result = reader.capture()

    assert result == b"real-fake-screen-png-bytes"


def test_capture_raises_loudly_on_a_real_failure():
    with patch("PIL.ImageGrab.grab", side_effect=RuntimeError("no display available")):
        reader = ScreenReader(gemini_provider=_FakeGeminiProvider())
        with pytest.raises(ScreenReaderError, match="no display available"):
            reader.capture()


def test_read_screen_captures_and_understands_in_one_real_call():
    fake_provider = _FakeGeminiProvider(description="A real desktop showing a browser window.")
    with patch("PIL.ImageGrab.grab", return_value=_fake_pil_image()):
        reader = ScreenReader(gemini_provider=fake_provider)
        observation = reader.read_screen()

    assert observation.text_content == "A real desktop showing a browser window."
    assert observation.url == "screen://local"
    assert len(fake_provider.calls) == 1
    assert fake_provider.calls[0][0] == b"real-fake-screen-png-bytes"


def test_read_screen_accepts_a_custom_real_prompt():
    fake_provider = _FakeGeminiProvider()
    with patch("PIL.ImageGrab.grab", return_value=_fake_pil_image()):
        reader = ScreenReader(gemini_provider=fake_provider)
        reader.read_screen(prompt="Is there an error dialog visible?")

    assert fake_provider.calls[0][1] == "Is there an error dialog visible?"


def test_a_real_provider_failure_during_understanding_is_wrapped_loudly():
    class _FailingProvider:
        name = "failing"

        def understand_image(self, image_bytes, prompt, media_type="image/png"):
            from atlas.integrations.gemini_provider import GeminiProviderError

            raise GeminiProviderError("real vision outage")

    with patch("PIL.ImageGrab.grab", return_value=_fake_pil_image()):
        reader = ScreenReader(gemini_provider=_FailingProvider())
        with pytest.raises(ScreenReaderError, match="real vision outage"):
            reader.read_screen()


def test_name_is_screen():
    assert ScreenReader(gemini_provider=_FakeGeminiProvider()).name == "screen"
