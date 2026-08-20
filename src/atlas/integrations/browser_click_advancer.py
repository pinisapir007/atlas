"""VerifiedClickAdvancer (2026-08-15, Digital Body Foundation) -- the
narrow, single-purpose click primitive proven twice, ad-hoc, in scratch
scripts during the M1 Marketplace pagination work (Page 1->2, Page 2->3),
now a real, tested module instead of copy-pasted session logic.

Deliberately as narrow as DiscoveryScrollAdvancer: this module imports and
can dispatch nothing except browser_use.browser.events.ClickElementEvent
-- no Tools, no forms, no text input, no navigate-to-arbitrary-url. The
one real action is a single click on a target selected deterministically
by a caller-supplied href predicate, never a coordinate, a fuzzy match, or
an LLM guess.

Reuses the exact same safety-gate ordering already proven in
DiscoveryScrollAdvancer._advance_async() (select target -> verify_target
before -> the one real action -> bounded content-change wait ->
verify_target after) and the same real select_target_by_url() -- an
import, not a second copy.

Target selection discipline (proven live, twice): among every <a> node
whose real href attribute satisfies the caller's `href_matches`
predicate, 0 matches is a hard failure and more than one DISTINCT href
value among the matches is also a hard failure (ambiguous -- never guess
which one) -- but multiple nodes that all share the exact same real href
are not ambiguous, and the first is used.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable

from atlas.integrations.browser_use_observer import BrowserUseError, select_target_by_url


@dataclass
class ClickAdvanceResult:
    """One real click cycle's outcome. `clicked_href` records exactly
    which real href was matched and clicked -- part of the auditable
    provenance every real action in this codebase carries."""

    text_content: str
    url: str
    content_changed: bool
    clicked_href: str


class VerifiedClickAdvancer:
    """The one, narrow action this class can perform: a single, bounded
    ClickElementEvent on a deterministically-selected, already-verified
    target, followed by a bounded, read-only wait for real content
    change. Structurally incapable of input/submit/upload/send_keys/
    navigate-to-arbitrary-url -- none of browser_use's Tools action
    registry is imported here, and no form-interaction event is either."""

    name = "verified_click_advancer"

    def __init__(self, cdp_url: str | None = None):
        self._cdp_url = cdp_url

    def click(
        self,
        url: str,
        href_matches: Callable[[str], bool],
        verify_target: Callable[[str], bool] | None = None,
        content_changed: Callable[[str], bool] | None = None,
        content_change_timeout: float = 15.0,
        select_existing_target: bool = True,
    ) -> ClickAdvanceResult:
        """`href_matches` is a real predicate over a raw href string
        (e.g. an exact-string comparison against a known pagination URL)
        -- this class has no domain knowledge of what a "next page" or
        "product link" looks like, by design, the same reusability
        discipline DiscoveryScrollAdvancer's `content_changed` already
        establishes.

        Fail-closed target selection: 0 real <a> nodes whose href
        satisfies `href_matches` -> BrowserUseError. More than one
        DISTINCT href among the matches -> BrowserUseError (ambiguous,
        never guessed). One or more nodes sharing the exact same real
        href -> the first is clicked, since they are, by definition, the
        same real target."""
        try:
            return asyncio.run(
                self._click_async(
                    url, href_matches, verify_target, content_changed, content_change_timeout, select_existing_target
                )
            )
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise BrowserUseError(f"real browser-use failure clicking within {url!r}: {exc}") from exc

    async def _click_async(
        self,
        url: str,
        href_matches: Callable[[str], bool],
        verify_target: Callable[[str], bool] | None,
        content_changed: Callable[[str], bool] | None,
        content_change_timeout: float,
        select_existing_target: bool,
    ) -> ClickAdvanceResult:
        from browser_use import BrowserSession
        from browser_use.browser.events import ClickElementEvent

        session = BrowserSession(cdp_url=self._cdp_url)
        await session.start()
        try:
            if select_existing_target:
                await select_target_by_url(session, url)

            real_url = await session.get_current_page_url()
            if verify_target is not None and not verify_target(real_url):
                raise BrowserUseError(
                    f"real target before click is not within the approved scope: {real_url!r} (requested {url!r})"
                )

            summary = await session.get_browser_state_summary()
            selector_map = summary.dom_state.selector_map
            matches = [
                (node, getattr(node, "attributes", {}) or {})
                for node in selector_map.values()
                if getattr(node, "tag_name", "").lower() == "a"
            ]
            matches = [(node, attrs) for node, attrs in matches if href_matches(attrs.get("href", ""))]

            if not matches:
                raise BrowserUseError(f"no real <a> href within {url!r} satisfied href_matches — 0 matches, fail-closed")
            distinct_hrefs = {attrs.get("href", "") for _, attrs in matches}
            if len(distinct_hrefs) > 1:
                raise BrowserUseError(
                    f"ambiguous target within {url!r}: {len(distinct_hrefs)} distinct real hrefs matched — fail-closed, never guessed"
                )

            chosen_node, chosen_attrs = matches[0]
            clicked_href = chosen_attrs.get("href", "")

            # The one and only real action this class performs. No
            # Tools, no input/submit/upload/send_keys/navigate --
            # ClickElementEvent is dispatched directly on the event bus,
            # the same real, public mechanism browser_use's own
            # tools/service.py uses internally.
            event = session.event_bus.dispatch(ClickElementEvent(node=chosen_node, button="left"))
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
            if verify_target is not None and not verify_target(real_url_after):
                raise BrowserUseError(
                    f"real target after click is not within the approved scope: {real_url_after!r} (requested {url!r})"
                )

            return ClickAdvanceResult(
                text_content=text_content, url=real_url_after, content_changed=changed, clicked_href=clicked_href
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
        """Same bounded, read-only polling as
        DiscoveryScrollAdvancer._poll_until_content_changed() -- a
        timeout is a legitimate outcome here too (a click that didn't
        change anything visible is still a real, reportable fact, not
        necessarily a failure the caller must treat as unexpected)."""
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
