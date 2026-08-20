"""VerifiedButtonClickAdvancer (2026-08-17, Final Live Eyes Navigation
Test) -- the narrow, single-purpose primitive for clicking a real,
structurally-verified <button> element, mirroring VerifiedClickAdvancer's
exact safety discipline (select target -> verify_target before -> the
one real action -> bounded content-change wait -> verify_target after),
extended to the one real, live-confirmed case VerifiedClickAdvancer
structurally cannot handle: Digistore24's real in-app product-detail
"Back" control renders as a <button class="back ng-star-inserted">, not
an <a href> -- confirmed by direct, live DOM inspection (2026-08-17),
not assumed. VerifiedClickAdvancer only ever considers <a> nodes at all,
by design; this module exists specifically because a real, needed
control has no href to match against.

Deliberately as narrow as VerifiedClickAdvancer: imports and can
dispatch nothing except ClickElementEvent -- no Tools, no forms, no
text input, no navigate-to-arbitrary-url. Matched by a caller-supplied
predicate over a button's real, observed attributes (never text content,
never a guess) -- 0 matches is a hard failure, more than one DISTINCT
matching node is also a hard failure (ambiguous -- never guessed),
mirroring VerifiedClickAdvancer's own real href-ambiguity discipline
exactly, one level removed (attributes instead of href).

Additional, unconditional safety gate beyond the caller's own predicate
(defense in depth, not delegated entirely to the caller): a node whose
real `type` attribute is `"submit"`, or whose real `attributes` contain
`formaction`/`name`/`value` (the real, structural markers of a form-
submission control), is NEVER clicked by this class, regardless of what
the caller's predicate says -- a caller mistake can never turn this into
a form-submission primitive.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable

from atlas.integrations.browser_use_observer import BrowserUseError, select_target_by_url

_FORM_SUBMISSION_MARKERS = ("formaction", "name", "value")


@dataclass
class ButtonClickAdvanceResult:
    """One real button-click cycle's outcome. `clicked_attributes`
    records the real, matched button's own attributes -- part of the
    auditable provenance every real action in this codebase carries."""

    text_content: str
    url: str
    content_changed: bool
    clicked_attributes: dict


class VerifiedButtonClickAdvancer:
    """The one, narrow action this class can perform: a single, bounded
    ClickElementEvent on a deterministically-selected, already-verified
    <button> target, followed by a bounded, read-only wait for real
    content change. Structurally incapable of input/submit/upload/
    send_keys/navigate-to-arbitrary-url -- none of browser_use's Tools
    action registry is imported here, and no form-interaction event is
    either."""

    name = "verified_button_click_advancer"

    def __init__(self, cdp_url: str | None = None):
        self._cdp_url = cdp_url

    def click(
        self,
        url: str,
        attributes_match: Callable[[dict], bool],
        verify_target: Callable[[str], bool] | None = None,
        content_changed: Callable[[str], bool] | None = None,
        content_change_timeout: float = 15.0,
        select_existing_target: bool = True,
    ) -> ButtonClickAdvanceResult:
        """`attributes_match` is a real predicate over a raw <button>
        node's real attributes dict -- this class has no domain
        knowledge of what a "Back" button looks like, by design, the
        same reusability discipline VerifiedClickAdvancer's
        `href_matches` already establishes.

        Fail-closed target selection: 0 real <button> nodes whose
        attributes satisfy `attributes_match` (after the unconditional
        form-submission-marker exclusion below) -> BrowserUseError. More
        than one DISTINCT matching node -> BrowserUseError (ambiguous,
        never guessed). One or more nodes sharing the exact same real
        attributes -> the first is clicked, since they are, by
        definition, the same real target."""
        try:
            return asyncio.run(
                self._click_async(url, attributes_match, verify_target, content_changed, content_change_timeout, select_existing_target)
            )
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise BrowserUseError(f"real browser-use failure clicking a button within {url!r}: {exc}") from exc

    async def _click_async(
        self,
        url: str,
        attributes_match: Callable[[dict], bool],
        verify_target: Callable[[str], bool] | None,
        content_changed: Callable[[str], bool] | None,
        content_change_timeout: float,
        select_existing_target: bool,
    ) -> ButtonClickAdvanceResult:
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
                    f"real target before button click is not within the approved scope: {real_url!r} (requested {url!r})"
                )

            summary = await session.get_browser_state_summary()
            selector_map = summary.dom_state.selector_map
            matches = [
                (node, getattr(node, "attributes", {}) or {})
                for node in selector_map.values()
                if getattr(node, "tag_name", "").lower() == "button"
            ]
            # Unconditional defense-in-depth: never a form-submission-shaped button, no matter what the caller's predicate says.
            matches = [
                (node, attrs) for node, attrs in matches
                if attrs.get("type") != "submit" and not any(marker in attrs for marker in _FORM_SUBMISSION_MARKERS)
            ]
            matches = [(node, attrs) for node, attrs in matches if attributes_match(attrs)]

            if not matches:
                raise BrowserUseError(f"no real <button> within {url!r} satisfied attributes_match — 0 matches, fail-closed")
            distinct = {tuple(sorted(attrs.items())) for _, attrs in matches}
            if len(distinct) > 1:
                raise BrowserUseError(
                    f"ambiguous button target within {url!r}: {len(distinct)} distinct real matches — fail-closed, never guessed"
                )

            chosen_node, chosen_attrs = matches[0]

            # The one and only real action this class performs.
            event = session.event_bus.dispatch(ClickElementEvent(node=chosen_node, button="left"))
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)

            if content_changed is not None:
                changed, text_content = await self._poll_until_content_changed(session, content_changed, content_change_timeout)
            else:
                changed = False
                text_content = await session.get_state_as_text()

            real_url_after = await session.get_current_page_url()
            if verify_target is not None and not verify_target(real_url_after):
                raise BrowserUseError(
                    f"real target after button click is not within the approved scope: {real_url_after!r} (requested {url!r})"
                )

            return ButtonClickAdvanceResult(
                text_content=text_content, url=real_url_after, content_changed=changed, clicked_attributes=chosen_attrs
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
