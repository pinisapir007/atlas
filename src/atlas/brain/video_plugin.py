"""VideoPlugin (2026-08-09, Hearing V1) — the real KnowledgeSourcePlugin
implementation for local video files. Video Understanding and MP4 are
one real capability: a single real multimodal call to Gemini (via
GeminiProvider.understand_video) -- audio and video streams are
processed together by Gemini natively (per the official docs), so a
video's spoken/ambient audio is already covered by this same call,
with no separate audio-extraction step needed. Mirrors ImagePlugin/
AudioPlugin's exact structure.

Reuses ResourceAllowlist, the same real local-file-access gate every
other local-file plugin in this codebase already establishes.
"""

from pathlib import Path

from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.integrations.base import PageObservation
from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError

SUPPORTED_SUFFIXES = {".mp4", ".mpeg", ".mov", ".avi", ".flv", ".mpg", ".webm", ".wmv"}

_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mov": "video/mov",
    ".avi": "video/x-msvideo",
    ".flv": "video/x-flv",
    ".mpg": "video/mpg",
    ".webm": "video/webm",
    ".wmv": "video/wmv",
}

_UNDERSTAND_PROMPT = (
    "Describe what is shown and said in this real video in detail (visuals, spoken audio, timeline of events). "
    "If there is spoken content, transcribe the key parts verbatim. "
    "If there is no meaningful content, say so honestly rather than inventing any."
)


class VideoPluginError(Exception):
    """A real failure reading or understanding a video file — never
    swallowed into a fabricated/partial observation, the same
    loud-failure discipline every other real plugin in this codebase
    already establishes."""


class PathNotApprovedError(ValueError):
    """Raised when `source_ref` is not within a real, founder-approved
    folder on the real ResourceAllowlist — the same fail-closed check
    ImagePlugin/AudioPlugin/DocumentPlugin already perform."""


class VideoPlugin:
    """Real KnowledgeSourcePlugin for local video. `name` satisfies the
    Protocol structurally (duck-typed, @runtime_checkable), the same
    pattern every other real provider in this codebase uses."""

    name = "video"

    def __init__(self, allowlist: ResourceAllowlist | None = None, gemini_provider: GeminiProvider | None = None):
        self._allowlist = allowlist if allowlist is not None else ResourceAllowlist()
        self._gemini = gemini_provider if gemini_provider is not None else GeminiProvider()

    def can_handle(self, source_ref: str) -> bool:
        return Path(source_ref).suffix.lower() in SUPPORTED_SUFFIXES

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        video_bytes, path = self._read_approved_video(source_ref)
        mime_type = _MIME_TYPES[path.suffix.lower()]

        try:
            description = self._gemini.understand_video(video_bytes, _UNDERSTAND_PROMPT, mime_type=mime_type)
            structured_data = {}
            if extract:
                structured_data = self._gemini.understand_video_structured(
                    video_bytes, "Watch this real video.", extract, mime_type=mime_type
                )
        except GeminiProviderError as exc:
            raise VideoPluginError(str(exc)) from exc

        return PageObservation(
            url=str(path.resolve()),
            title=path.name,
            text_content=description,
            structured_data=structured_data,
        )

    def _read_approved_video(self, source_ref: str) -> tuple[bytes, Path]:
        if not self._allowlist.is_approved(source_ref):
            raise PathNotApprovedError(f"path not approved for autonomous reading: {source_ref!r}")

        path = Path(source_ref)
        if not path.is_file():
            raise VideoPluginError(f"real file not found: {source_ref!r}")

        try:
            return path.read_bytes(), path
        except OSError as exc:
            raise VideoPluginError(f"real failure reading {source_ref!r}: {exc}") from exc
