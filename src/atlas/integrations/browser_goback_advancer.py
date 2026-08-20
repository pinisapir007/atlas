"""VerifiedGoBackAdvancer (2026-08-17, Live Eyes Test 4 Root-Cause Fix) --
the narrow, single-purpose browser-history-back primitive, mirroring
VerifiedClickAdvancer's exact shape and safety discipline (this module's
whole reason to exist: DiscoveryScrollAdvancer/VerifiedClickAdvancer
already proved this "one narrow event, verified before and after" shape
is the right one, twice -- this is the third, not a fourth pattern).

Root cause of the real Live Eyes Test 4 session loss (2026-08-17): the
previous live attempt returned to the Marketplace listing via a plain
BrowserUseObserver.observe(listing_url) call with no target-reuse flags
set -- which falls through to a genuine browser_use `navigate_to()`
(a real CDP Page.navigate, a hard reload) even though the domain/URL
were correct and the session WAS authenticated. Digistore24's app
responded to that hard reload by redirecting to a real login/
autologin=clear URL -- a real, live-confirmed fact, not a guess.

browser_use.browser.events.GoBackEvent (confirmed real and wired --
DefaultActionWatchdog.on_GoBackEvent, auto-registered via
watchdog_base.attach_to_session()'s on_*Event reflection, independent of
the misleading commented-out explicit registration line in session.py)
dispatches a real CDP `Page.navigateToHistoryEntry` -- a genuine browser
"back" navigation through the SAME tab's own history, the same real
mechanism a user's physical back-button press would trigger, and
structurally different from a fresh `Page.navigate()` reload: an SPA
that opened its product-detail view via client-side routing (pushState)
is restored via its own in-app history, never a hard server round trip.
This is the real, evidence-based reason to prefer it over any URL-based
"return" for this specific site's behavior.

Deliberately as narrow as VerifiedClickAdvancer: imports and can
dispatch nothing except GoBackEvent -- no Tools, no forms, no click, no
navigate-to-arbitrary-url. on_GoBackEvent's own real implementation
never raises when there is no history to go back to -- it logs a
warning and silently returns -- so this class NEVER trusts the dispatch
call alone as proof of success; the real post-condition (verify_target
against the real, freshly-read URL after) is what determines success,
matching the "do not assume return succeeded merely because a browser
command succeeded" discipline this fix exists to establish.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable

from atlas.integrations.browser_use_observer import BrowserUseError


@dataclass
class GoBackResult:
    """One real go-back cycle's outcome."""

    text_content: str
    url: str
    content_changed: bool


class VerifiedGoBackAdvancer:
    """The one, narrow action this class can perform: a single, bounded
    GoBackEvent (real browser-history-back, never a URL-based
    navigation), followed by a bounded, read-only wait for real content
    change, then a mandatory real target re-verification. Structurally
    incapable of click/input/submit/upload/send_keys/navigate-to-
    arbitrary-url -- GoBackEvent is the only event this module ever
    imports or dispatches."""

    name = "verified_goback_advancer"

    def __init__(self, cdp_url: str | None = None):
        self._cdp_url = cdp_url

    def go_back(
        self,
        verify_target: Callable[[str], bool],
        content_changed: Callable[[str], bool] | None = None,
        content_change_timeout: float = 15.0,
    ) -> GoBackResult:
        """`verify_target` is REQUIRED (not optional, unlike
        VerifiedClickAdvancer's own -- a return whose destination is
        never checked is exactly the unsafe pattern this module exists
        to close) -- checked against the real, freshly-read URL after
        the go-back attempt. Raises BrowserUseError if the real
        destination isn't approved (this is precisely how a real
        redirect toward a login/logout page is caught and refused,
        never silently treated as "returned"), or if the real URL
        doesn't change at all when the caller expected it to (see
        `content_changed`)."""
        try:
            return asyncio.run(self._go_back_async(verify_target, content_changed, content_change_timeout))
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise BrowserUseError(f"real browser-use failure going back: {exc}") from exc

    async def _go_back_async(
        self,
        verify_target: Callable[[str], bool],
        content_changed: Callable[[str], bool] | None,
        content_change_timeout: float,
    ) -> GoBackResult:
        from browser_use import BrowserSession
        from browser_use.browser.events import GoBackEvent

        session = BrowserSession(cdp_url=self._cdp_url)
        await session.start()
        try:
            # The one and only real action this class performs -- native
            # browser-history back, dispatched on the real, public event
            # bus, the same mechanism VerifiedClickAdvancer/
            # DiscoveryScrollAdvancer already use for their own one real
            # action each.
            event = session.event_bus.dispatch(GoBackEvent())
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)

            if content_changed is not None:
                changed, text_content = await self._poll_until_content_changed(
                    session, content_changed, content_change_timeout
                )
            else:
                changed = False
                text_content = await session.get_state_as_text()

            real_url_after = await session.get_current_page_url()
            if not verify_target(real_url_after):
                raise BrowserUseError(
                    f"real destination after go-back is not within the approved scope: {real_url_after!r} -- "
                    "never trust a go-back command's own success alone"
                )

            return GoBackResult(text_content=text_content, url=real_url_after, content_changed=changed)
        finally:
            await session.stop()

    async def _poll_until_content_changed(
        self,
        session,
        content_changed: Callable[[str], bool],
        timeout: float,
        poll_interval: float = 0.5,
    ) -> tuple[bool, str]:
        """Same bounded, read-only polling as VerifiedClickAdvancer's own
        -- a timeout is a legitimate outcome (a go-back that produced no
        visible content change is still a real, reportable fact)."""
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
