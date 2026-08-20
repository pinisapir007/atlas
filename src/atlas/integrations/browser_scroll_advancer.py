"""DiscoveryScrollAdvancer (2026-08-14, M1 Autonomous Marketplace
Discovery Loop) -- the narrow, single-purpose browser primitive that
advances a virtualized/lazy-loaded list view by dispatching one real
browser_use ScrollEvent, then waits for real content-set change.

Deliberately a much narrower capability surface than the general-purpose
browser executor elsewhere in this codebase: this module imports and can
dispatch nothing except browser_use.browser.events.ScrollEvent -- no
action-call registry, no click/input/upload/keystroke/navigate
capability exists anywhere here (confirmed structurally, not just by
convention -- see test_browser_scroll_advancer.py's static source-check
test, the same discipline test_m1_marketplace_discovery_safety_wiring.py
already established for BrowserUseObserver).

Reuses the exact same safety-gate ordering already proven in
BrowserUseObserver._observe_async() (select target -> verify_target
before -> [the one real action] -> bounded wait -> re-resolve URL ->
verify_target after) and the same real, already-tested
select_target_by_url() fail-closed target selection -- an import, not a
second copy of that logic.

Live-verified (2026-08-14, Single Live Scroll Validation): a single
ScrollEvent(direction="down", amount=1500) against the real Digistore24
Affiliate Marketplace produced 4 new, real product records, and one
previously-seen record no longer appeared in the same snapshot -- direct,
live evidence the list is virtualized/lazy-loaded, not a fully rendered
DOM. This is exactly why MarketplaceCatalogStore (marketplace_catalog.py)
is cumulative/union-based, never a mirror of the latest snapshot.

Bidirectional (2026-08-15, Digital Body Foundation): `direction` accepts
"up" as well as "down" (default, 100% backward compatible), fail-closed
on anything else -- the mirror-image extension the M1 Page 2/3 completion
work found real evidence it needed twice (an unwrapped, unsafe raw
ScrollEvent(direction="up") in a scratch script, and a news-reading
scenario needing "return to a point within a long page" independently).
Same safety gates for both directions, unconditionally -- this is one
more parameter on the exact same method, not a second class.

`include_dom` (also 2026-08-15) optionally captures
session.get_browser_state_summary().dom_state.selector_map in the SAME
browser-state moment as the final text read -- the "48317 lesson"
(text and DOM reads must come from one continuous session, never two
separate attaches) now structurally guaranteed by this class itself,
rather than a discipline scratch scripts had to remember by hand.

Orientation (also 2026-08-15): scroll_pages_above()/scroll_pages_below()
expose a real signal that already exists in every text_content capture --
browser_use's own scroll-region accounting ("N.N pages above"/"N.N pages
below", emitted verbatim for a scrollable container). Only the "below"
half had a reader before now (marketplace_extraction.scroll_pages_below(),
which stays exactly where it is -- an existing, tested, working import
path this module doesn't touch); this adds the symmetric "above" half
and re-exposes both here, generically, since knowing whether a reverse
scroll actually made progress (or already reached the top) has nothing
to do with Marketplace product parsing specifically -- it belongs with
the scroll primitive itself, not one domain's extraction module.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Callable

from atlas.integrations.browser_use_observer import BrowserUseError, select_target_by_url

_VALID_DIRECTIONS = {"up", "down"}
_PAGES_ABOVE_RE = re.compile(r"([\d.]+) pages above")
_PAGES_BELOW_RE = re.compile(r"([\d.]+) pages below")


def scroll_pages_above(text_content: str) -> float | None:
    """None when no such line is present (nothing scrollable, or already
    at the very top) -- never a fabricated 0.0 standing in for "unknown".
    A real 0.0 (the line present, reading "0.0 pages above") IS a
    meaningful, distinct signal: genuinely at the top, not merely
    unmeasured."""
    match = _PAGES_ABOVE_RE.search(text_content)
    return float(match.group(1)) if match else None


def scroll_pages_below(text_content: str) -> float | None:
    """Same real signal, same reading, as
    marketplace_extraction.scroll_pages_below() -- kept as a second,
    generic entry point here (not a re-export) so a caller working
    purely at the Digital Body layer never has to import a Marketplace-
    named module just to read scroll position. Both read the exact same
    real browser_use text annotation; neither is more authoritative."""
    match = _PAGES_BELOW_RE.search(text_content)
    return float(match.group(1)) if match else None


@dataclass
class ScrollAdvanceResult:
    """One real scroll cycle's outcome. `content_changed` is False, not
    an error, when the bounded wait simply timed out without any real
    change -- a legitimate outcome (e.g. the end of the list was
    reached), not a failure the caller should treat as unexpected.
    `selector_map` is None unless `include_dom=True` was requested --
    when present, it was captured in the same browser-state moment as
    `text_content`, never a separate, later read.

    `dom_root` (2026-08-16, Semantic Grounding Wiring -- Blocker 2 root
    cause fix): the full simplified DOM tree
    (`get_browser_state_summary().dom_state._root`), captured in the
    exact same call as `selector_map` -- zero extra browser round-trip.
    Added because `selector_map` was live-proven (3 consecutive identical
    reads, no action between them, ruling out timing/lazy-render/
    virtualization) to silently OMIT real, tooltip-bearing icon nodes
    that a full tree walk of `_root` finds reliably every time --
    `selector_map` is browser-use's interactive-element index, evidently
    capped/filtered independently of whether a node carries a real
    matTooltip. Callers needing a non-interactive attribute (like a real
    semantic tooltip) must walk `dom_root`, never `selector_map` --
    `href_map`-style callers (interactive `<a>` targets) are unaffected
    and can keep using `selector_map` exactly as before."""

    text_content: str
    url: str
    content_changed: bool
    selector_map: object | None = None
    dom_root: object | None = None


class DiscoveryScrollAdvancer:
    """The one, narrow action this class can perform: a single, bounded
    ScrollEvent (up or down) on an already-attached, already-target-
    verified page, followed by a bounded, read-only wait for real content
    change. Structurally incapable of click/input/submit/navigate/upload
    -- none of browser_use's Tools action registry is imported here."""

    name = "discovery_scroll_advancer"

    def __init__(self, cdp_url: str | None = None):
        self._cdp_url = cdp_url

    def advance(
        self,
        url: str,
        verify_target: Callable[[str], bool] | None = None,
        content_changed: Callable[[str], bool] | None = None,
        content_change_timeout: float = 15.0,
        scroll_amount_px: int = 1500,
        select_existing_target: bool = True,
        direction: str = "down",
        include_dom: bool = False,
    ) -> ScrollAdvanceResult:
        """Synchronous entry point, same asyncio.run() bridge pattern as
        BrowserUseObserver.observe(). `content_changed`, when given, is a
        real predicate over get_state_as_text()'s raw text (the caller
        builds it -- e.g. "the extracted product-key set differs from
        before"); this class has no domain knowledge of what "new
        content" means, by design, so it stays reusable for any
        virtualized-list discovery, not just the Marketplace.

        `direction` is validated BEFORE any browser session starts --
        fail fast on a bad caller value, never a wasted real action.

        Safety-gate order (mirrors BrowserUseObserver._observe_async()
        exactly): select_existing_target (fail-closed, exact match) ->
        verify_target against the real pre-scroll URL -> the one
        ScrollEvent -> bounded content-change poll -> verify_target again
        against a freshly re-resolved real URL. A target/domain mismatch
        at either check raises BrowserUseError -- loudly fail-closed,
        never a silently-returned "stopped" result, the same discipline
        every other verify_target failure in this codebase already has.
        This holds identically for direction="up" -- reverse traversal
        can never leave the verified target/domain either."""
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(f"direction must be one of {sorted(_VALID_DIRECTIONS)}, got {direction!r}")
        try:
            return asyncio.run(
                self._advance_async(
                    url,
                    verify_target,
                    content_changed,
                    content_change_timeout,
                    scroll_amount_px,
                    select_existing_target,
                    direction,
                    include_dom,
                )
            )
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise BrowserUseError(f"real browser-use failure advancing {url!r}: {exc}") from exc

    async def _advance_async(
        self,
        url: str,
        verify_target: Callable[[str], bool] | None,
        content_changed: Callable[[str], bool] | None,
        content_change_timeout: float,
        scroll_amount_px: int,
        select_existing_target: bool,
        direction: str,
        include_dom: bool,
    ) -> ScrollAdvanceResult:
        from browser_use import BrowserSession
        from browser_use.browser.events import ScrollEvent

        session = BrowserSession(cdp_url=self._cdp_url)
        await session.start()
        try:
            if select_existing_target:
                await select_target_by_url(session, url)

            real_url = await session.get_current_page_url()
            if verify_target is not None and not verify_target(real_url):
                raise BrowserUseError(
                    f"real target before scroll is not within the approved scope: {real_url!r} (requested {url!r})"
                )

            # The one and only real action this class performs. No Tools,
            # no click/input/submit/navigate -- ScrollEvent is dispatched
            # directly on the event bus, the same real, public mechanism
            # browser_use's own tools/service.py uses internally.
            event = session.event_bus.dispatch(ScrollEvent(direction=direction, amount=scroll_amount_px, node=None))
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)

            if content_changed is not None:
                changed, text_content = await self._poll_until_content_changed(
                    session, content_changed, content_change_timeout
                )
            else:
                changed = False
                text_content = await session.get_state_as_text()

            # Captured in this same session moment, right alongside the
            # final text_content above -- never a second, later attach
            # (the "48317 lesson").
            selector_map = None
            dom_root = None
            if include_dom:
                summary = await session.get_browser_state_summary()
                selector_map = summary.dom_state.selector_map
                dom_root = summary.dom_state._root

            real_url_after = await session.get_current_page_url()
            if verify_target is not None and not verify_target(real_url_after):
                raise BrowserUseError(
                    f"real target after scroll is not within the approved scope: {real_url_after!r} (requested {url!r})"
                )

            return ScrollAdvanceResult(
                text_content=text_content, url=real_url_after, content_changed=changed,
                selector_map=selector_map, dom_root=dom_root,
            )
        finally:
            await session.stop()

    async def _poll_until_content_changed(
        self,
        session,
        content_changed: Callable[[str], bool],
        timeout: float,
        poll_interval: float = 0.5,
    ) -> tuple[bool, str]:
        """Bounded, read-only polling on the same public get_state_as_text()
        BrowserUseObserver already uses -- never a fixed sleep. Unlike
        BrowserUseObserver._wait_for_page_ready() (which raises on
        timeout, because "not ready yet" is always a real failure for a
        plain observation), a timeout here is a legitimate, expected
        outcome -- the list may genuinely have no more content below the
        current position -- so this returns (False, last_text) rather
        than raising, leaving what a timeout *means* to the caller's own
        stop-condition logic."""
        start = asyncio.get_event_loop().time()
        text = await session.get_state_as_text()
        while True:
            if content_changed(text):
                return True, text
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                return False, text
            await asyncio.sleep(poll_interval)
            text = await session.get_state_as_text()
