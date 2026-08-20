"""BrowserPlugin (2026-08-06, Knowledge Sources V1) — the real
KnowledgeSourcePlugin implementation wrapping the existing, real,
already-live-verified BrowserObserver + BrowserAllowlist. Proves the
plugin claim on the very first source it's applied to: a real domain-
approval failure and a real successful observation both behave
identically to how atlas.brain.browser_research.collect_evidence_
from_url already behaved before this module existed — this is a real
adapter, not a rewrite.
"""

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.integrations.base import BrowserObserver, PageObservation
from atlas.integrations.browser_observer_registry import get_browser_observer


class DomainNotApprovedError(ValueError):
    """Raised when the real domain in `source_ref` is not on the real
    BrowserAllowlist — the same fail-closed check
    browser_research.collect_evidence_from_url already performs,
    reused here rather than re-derived."""


class BrowserPlugin:
    """Real KnowledgeSourcePlugin for web sources. `name` satisfies
    the Protocol structurally (duck-typed, @runtime_checkable), the
    same pattern every other real provider in this codebase uses."""

    name = "browser"

    def __init__(self, observer: BrowserObserver | None = None, allowlist: BrowserAllowlist | None = None):
        self._observer = observer if observer is not None else get_browser_observer("browser_use")
        self._allowlist = allowlist if allowlist is not None else BrowserAllowlist()

    def can_handle(self, source_ref: str) -> bool:
        return source_ref.startswith("http://") or source_ref.startswith("https://")

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        if not self._allowlist.is_approved(source_ref):
            raise DomainNotApprovedError(f"domain not approved for autonomous browsing: {source_ref!r}")
        # verify_target (2026-08-13, M1 Marketplace Discovery Safety
        # Wiring): passed through so a real BrowserObserver implementation
        # that honors it (e.g. BrowserUseObserver) catches a redirect
        # *before* page text/screenshot are ever read. The post-observe
        # re-check below stays as defense-in-depth for any implementation
        # that doesn't honor verify_target (the parameter is optional).
        observation = self._observer.observe(source_ref, extract=extract, verify_target=self._allowlist.is_approved)
        if not self._allowlist.is_approved(observation.url):
            raise DomainNotApprovedError(
                f"real destination after navigation/redirect is not approved: {observation.url!r} (requested {source_ref!r})"
            )
        return observation
