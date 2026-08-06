"""KNOWLEDGE_SOURCE_PLUGINS registry (2026-08-06, Knowledge Sources
V1) — the actual mechanism behind "ATLAS learns from any relevant
knowledge source without the core needing to change." Two real
plugins from day one: BrowserPlugin (web) and DocumentPlugin (local
text/Markdown). Adding a real future source (YouTube/TikTok/
Instagram/Facebook/podcasts, or any other real business knowledge
source) means one new class satisfying KnowledgeSourcePlugin plus one
entry in this list — never touching an existing plugin, this
dispatch function, or the loop that calls it.

`select_plugin` dispatches purely by each plugin's own `can_handle()`
— first match wins, so plugin order matters only when two plugins
could both structurally claim the same source_ref (not the case for
any two real plugins registered today).
"""

from atlas.brain.browser_plugin import BrowserPlugin
from atlas.brain.document_plugin import DocumentPlugin
from atlas.integrations.base import KnowledgeSourcePlugin

KNOWLEDGE_SOURCE_PLUGINS: list[KnowledgeSourcePlugin] = [
    BrowserPlugin(),
    DocumentPlugin(),
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
