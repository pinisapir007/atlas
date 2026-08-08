"""ScreenReader (2026-08-09, Vision V1) — real Windows desktop screen
capture + understanding. Reuses the exact same real mechanism
ImagePlugin already established (GeminiProvider.understand_image) —
a screen capture is just an image from a different real source, not
a new understanding capability.

Uses Pillow's `ImageGrab` (already installed, zero new dependency) —
the standard, real way to capture the Windows desktop.

Deliberately NOT gated by ResourceAllowlist, unlike DocumentPlugin/
ImagePlugin: there is no meaningful "which folder" scope for "the
current screen" the way there is for a file path — it is honestly
all-or-nothing. This is a real, meaningful privacy boundary worth
naming plainly: a screen capture can show whatever is genuinely
visible at that moment, not just ATLAS's own windows. Calling this
is a deliberate, real action, not something wired into any automatic
loop.
"""

import io

from atlas.integrations.base import PageObservation
from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError

_DEFAULT_PROMPT = (
    "Describe what is shown on this real screen capture in detail (visible windows, applications, "
    "content). Then, separately, transcribe any literal text visible verbatim, exactly as written -- "
    "if there is no readable text, say so honestly rather than inventing any."
)


class ScreenReaderError(Exception):
    """A real failure capturing or understanding the screen — never
    swallowed into a fabricated/partial observation, the same
    loud-failure discipline every other real plugin in this codebase
    already establishes."""


class ScreenReader:
    """Real screen-capture + understanding. Not a KnowledgeSourcePlugin
    (there is no real `source_ref` to dispatch on — "the current
    screen" is not addressable the way a URL or file path is), so this
    is a standalone real capability, called directly."""

    name = "screen"

    def __init__(self, gemini_provider: GeminiProvider | None = None):
        self._gemini = gemini_provider if gemini_provider is not None else GeminiProvider()

    def capture(self) -> bytes:
        """Real, live capture of the current Windows desktop. Raises
        ScreenReaderError on any real failure (e.g., no display
        available) rather than returning fabricated empty bytes."""
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab()
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:  # noqa: BLE001 -- any real capture failure surfaces loudly
            raise ScreenReaderError(f"real screen capture failed: {exc}") from exc

    def read_screen(self, prompt: str | None = None) -> PageObservation:
        """Captures the real, current screen and understands it in one
        real call. `prompt` overrides the default describe+transcribe
        instruction for a targeted real question."""
        image_bytes = self.capture()
        try:
            description = self._gemini.understand_image(image_bytes, prompt or _DEFAULT_PROMPT, media_type="image/png")
        except GeminiProviderError as exc:
            raise ScreenReaderError(str(exc)) from exc

        return PageObservation(url="screen://local", title="Windows Screen Capture", text_content=description)
