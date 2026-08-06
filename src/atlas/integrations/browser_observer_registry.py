"""BROWSER_OBSERVERS registry (2026-08-06, BrowserObserver V1) — empty
by design, the exact same shape as atlas.integrations.signal_registry:
no real BrowserObserver implementation is chosen yet. Picking a real
browser-automation backend (which library, which LLM drives its
natural-language extraction, how its credentials are supplied) is a
separate, explicit, architecturally significant decision — not
something this registry's existence implies is ready.

Everything upstream of this file (the BrowserObserver Protocol,
PageObservation, BrowserAllowlist, browser_research.collect_evidence_
from_url) is real, tested, and already integrated with the existing
KnowledgeBase/Finding/Decision Engine — none of it depends on this
registry being non-empty. This is intentionally the one and only file
that stays a stub until that separate decision is made.
"""

from atlas.integrations.base import BrowserObserver
from atlas.integrations.browser_use_observer import BrowserUseObserver

# The one real implementation, as of 2026-08-06 -- live-verified against
# a real page (example.com), real structured extraction (Gemini via the
# real GEMINI_API_KEY), and a real failure case (unresolvable domain).
BROWSER_OBSERVERS: dict[str, BrowserObserver] = {
    "browser_use": BrowserUseObserver(),
}


def get_browser_observer(name: str) -> BrowserObserver:
    if name not in BROWSER_OBSERVERS:
        raise ValueError(f"unsupported browser observer: {name!r} (supported: {sorted(BROWSER_OBSERVERS)})")
    return BROWSER_OBSERVERS[name]
