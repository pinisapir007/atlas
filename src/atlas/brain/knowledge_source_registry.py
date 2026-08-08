"""KNOWLEDGE_SOURCE_PLUGINS registry (2026-08-06, Knowledge Sources
V1) — the actual mechanism behind "ATLAS learns from any relevant
knowledge source without the core needing to change." Real plugins
registered today: BrowserPlugin (web), DocumentPlugin (local text/
Markdown), ImagePlugin (local images, Vision V1), and — as of
2026-08-09, Hearing V1 — AudioPlugin (local audio), VideoPlugin (local
video), YouTubePlugin (YouTube URLs specifically). Adding a real
future source (TikTok/Instagram/Facebook, or any other real business
knowledge source) means one new class satisfying KnowledgeSourcePlugin
plus one entry in this list — never touching an existing plugin, this
dispatch function, or the loop that calls it.

`select_plugin` dispatches purely by each plugin's own `can_handle()`
— first match wins, so plugin order DOES matter here: YouTubePlugin is
listed before BrowserPlugin specifically because a YouTube URL
structurally matches BrowserPlugin's generic http(s) check too, and
without this ordering a YouTube URL would be silently routed to
generic page-text reading (comments/chrome, not the actual video)
instead of real video/audio understanding.
"""

from atlas.brain.audio_plugin import AudioPlugin
from atlas.brain.browser_plugin import BrowserPlugin
from atlas.brain.document_plugin import DocumentPlugin
from atlas.brain.image_plugin import ImagePlugin
from atlas.brain.video_plugin import VideoPlugin
from atlas.brain.youtube_plugin import YouTubePlugin
from atlas.integrations.base import KnowledgeSourcePlugin

KNOWLEDGE_SOURCE_PLUGINS: list[KnowledgeSourcePlugin] = [
    YouTubePlugin(),
    BrowserPlugin(),
    DocumentPlugin(),
    ImagePlugin(),
    AudioPlugin(),
    VideoPlugin(),
]


def select_plugin(source_ref: str) -> KnowledgeSourcePlugin:
    """Returns the real, registered plugin that can handle
    `source_ref`, purely by structural format. Raises ValueError if
    no registered plugin recognizes it — the same fail-closed lookup
    discipline get_ai_provider/get_browser_observer already
    establish, never a silent fallback to the wrong plugin."""
    for plugin in KNOWLEDGE_SOURCE_PLUGINS:
        if plugin.can_handle(source_ref):
            return plugin
    raise ValueError(f"no registered knowledge source plugin can handle: {source_ref!r}")
