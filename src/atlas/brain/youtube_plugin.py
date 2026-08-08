"""YouTubePlugin (2026-08-09, Hearing V1) — real, direct YouTube URL
understanding, no download step: Gemini fetches and understands the
real public video directly from its URL. Covers YouTube Audio, Video
Understanding for YouTube specifically, and Podcast Understanding when
a podcast is hosted as a YouTube video (the common real case) -- all
the same real call as GeminiProvider.understand_youtube(), just
different prompts.

A YouTube URL structurally matches BrowserPlugin's can_handle() too
(any http(s):// URL) -- registered BEFORE BrowserPlugin in
knowledge_source_registry.py so "first match wins" routes it here,
to real video/audio understanding, instead of BrowserPlugin's generic
page-text reading (which would only see the page chrome/comments, not
the actual video content).

Reuses BrowserAllowlist, the same real founder-approved-domain gate
BrowserPlugin already established -- visiting a YouTube video is still
real autonomous access to a specific external domain, and gets no
free pass over any other web source.
"""

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.integrations.base import PageObservation
from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError

_UNDERSTAND_PROMPT = (
    "Describe what is shown and said in this real YouTube video in detail (visuals, spoken audio, "
    "timeline of key moments). If there is spoken content, summarize the key points. "
    "If the video is unavailable or has no meaningful content, say so honestly rather than inventing any."
)


class YouTubePluginError(Exception):
    """A real failure understanding a YouTube video — never swallowed
    into a fabricated/partial observation, the same loud-failure
    discipline every other real plugin in this codebase already
    establishes."""


class DomainNotApprovedError(ValueError):
    """Raised when youtube.com/youtu.be is not on the real
    BrowserAllowlist — the same fail-closed check BrowserPlugin
    already performs for every other web domain."""


class YouTubePlugin:
    """Real KnowledgeSourcePlugin for YouTube URLs. `name` satisfies
    the Protocol structurally (duck-typed, @runtime_checkable), the
    same pattern every other real provider in this codebase uses."""

    name = "youtube"

    def __init__(self, allowlist: BrowserAllowlist | None = None, gemini_provider: GeminiProvider | None = None):
        self._allowlist = allowlist if allowlist is not None else BrowserAllowlist()
        self._gemini = gemini_provider if gemini_provider is not None else GeminiProvider()

    def can_handle(self, source_ref: str) -> bool:
        lowered = source_ref.lower()
        return lowered.startswith(("http://", "https://")) and (
            "youtube.com" in lowered or "youtu.be" in lowered
        )

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        if not self._allowlist.is_approved(source_ref):
            raise DomainNotApprovedError(f"domain not approved for autonomous browsing: {source_ref!r}")

        try:
            description = self._gemini.understand_youtube(source_ref, _UNDERSTAND_PROMPT)
            structured_data = {}
            if extract:
                structured_data = self._gemini.understand_youtube_structured(
                    source_ref, "Watch this real YouTube video.", extract
                )
        except GeminiProviderError as exc:
            raise YouTubePluginError(str(exc)) from exc

        return PageObservation(
            url=source_ref,
            title=source_ref,
            text_content=description,
            structured_data=structured_data,
        )
