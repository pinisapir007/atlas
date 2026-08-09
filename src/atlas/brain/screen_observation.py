"""observe_and_record_screen() (2026-08-09) — the real bridge between
ScreenReader (Vision V1, real screen capture + understanding) and
KnowledgeBase (Memory V1, durable Findings + recall()). Built for a
real, concrete workflow the founder described: browsing a real
external site (e.g. a Digistore24 category page) on their own screen
while ATLAS reads and durably records what's shown, one real
observation at a time -- never a continuous background watcher (no
persistent process exists anywhere in ATLAS's real execution model,
the same honesty already established for browser_live_monitor.py).
Each call is one real, deliberate "look now" action; the founder
narrates page-to-page, ATLAS records page-to-page, and later
`recall()` retrieves what was seen ("what do we know about category
X") -- the exact mechanism that makes this a growing, durable business
knowledge base instead of a one-off screen read that's forgotten the
moment the terminal scrolls.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.screen_reader import ScreenReader, ScreenReaderError
from atlas.brain.models import Finding


def observe_and_record_screen(
    category: str,
    subject: str = "",
    market: str = "",
    prompt: str | None = None,
    screen_reader: ScreenReader | None = None,
    knowledge: KnowledgeBase | None = None,
) -> Finding:
    """Captures the real, current screen, understands it, and records
    it as a real Finding (source="screen_observation") -- reusing
    Finding's existing subject/market fields exactly as they're already
    used for web research, so a screen-observed product sits in the
    same real, searchable knowledge base as everything else. Raises
    ScreenReaderError on a real capture/understanding failure -- never
    records a fabricated or partial observation."""
    screen_reader = screen_reader if screen_reader is not None else ScreenReader()
    knowledge = knowledge if knowledge is not None else KnowledgeBase()

    observation = screen_reader.read_screen(prompt=prompt)

    finding = Finding(
        source="screen_observation",
        category=category,
        description=observation.text_content,
        evidence="local screen capture",
        subject=subject,
        market=market,
    )
    knowledge.save_finding(finding)
    return finding
