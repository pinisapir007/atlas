"""VerifiedTabCloseAdvancer (2026-08-17, Sales Page Safe Round Trip) --
the narrow, single-purpose primitive for closing exactly one, already-
identified real browser target/tab -- mirroring VerifiedGoBackAdvancer/
VerifiedClickAdvancer's exact safety discipline (verify before -> the
one real action -> verify after), extended to the one real, live-
confirmed case those two cannot handle: a Sales page link opens a real
NEW target (target="_blank"), and returning to the original Marketplace
target safely requires closing that new target -- never a browser-
history-back, never a re-navigation, never a guess.

Deliberately as narrow as its siblings: imports and can dispatch
nothing except browser_use.browser.events.CloseTabEvent -- no Tools, no
forms, no click, no navigate-to-arbitrary-url. CloseTabEvent is
confirmed real and directly wired (BrowserSession.on_CloseTabEvent,
explicitly registered rather than reflection-discovered) -- dispatches
a real CDP `Target.closeTarget` for exactly the target_id given, never
any other target.

Fail-closed, both directions: refuses to close a target_id that isn't
currently a real, open target (never closes "whatever's there"), and
refuses to report success unless the real, remaining target set,
re-read after the close, both no longer contains the closed target_id
AND still contains a real target matching `expected_remaining_url` --
a technically-successful close command is never trusted alone as proof
the original context survived.
"""

import asyncio
from dataclasses import dataclass


@dataclass
class TabCloseResult:
    """One real tab-close cycle's outcome -- the real, remaining page
    targets after the close, for the caller's own inspection."""

    closed_target_id: str
    remaining_target_ids: list[str]
    remaining_urls: list[str]


class TargetNotFoundError(ValueError):
    """Raised when `target_id_to_close` is not among the real, currently
    open page targets -- fail-closed, never closes an unverified/guessed
    target."""


class ExpectedTargetMissingError(ValueError):
    """Raised when, after closing the intended target, no real remaining
    page target matches `expected_remaining_url` -- the exact, narrow
    gate that proves the original context (e.g. the Marketplace tab)
    genuinely survived the close, never assumed."""


class VerifiedTabCloseAdvancer:
    """The one, narrow action this class can perform: closing exactly
    one, already-identified real target/tab, then verifying the real,
    remaining target set. Structurally incapable of navigation/click/
    input -- CloseTabEvent is the only event this module ever imports or
    dispatches."""

    name = "verified_tabclose_advancer"

    def __init__(self, cdp_url: str | None = None):
        self._cdp_url = cdp_url

    def close(self, target_id_to_close: str, expected_remaining_url: str, poll_timeout: float = 5.0) -> TabCloseResult:
        try:
            return asyncio.run(self._close_async(target_id_to_close, expected_remaining_url, poll_timeout))
        except (TargetNotFoundError, ExpectedTargetMissingError):
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise RuntimeError(f"real browser-use failure closing target {target_id_to_close!r}: {exc}") from exc

    async def _close_async(self, target_id_to_close: str, expected_remaining_url: str, poll_timeout: float) -> TabCloseResult:
        from browser_use import BrowserSession
        from browser_use.browser.events import CloseTabEvent

        session = BrowserSession(cdp_url=self._cdp_url)
        await session.start()
        try:
            targets_before = session.session_manager.get_all_page_targets()
            if not any(t.target_id == target_id_to_close for t in targets_before):
                raise TargetNotFoundError(
                    f"target_id {target_id_to_close!r} is not among the real, currently open page targets -- "
                    "fail-closed, never closing an unverified target"
                )

            event = session.event_bus.dispatch(CloseTabEvent(target_id=target_id_to_close))
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)

            # Real, live-confirmed timing gap (2026-08-17): the real CDP
            # Target.closeTarget call underlying CloseTabEvent completes
            # before session_manager's own internal target list has
            # necessarily processed the resulting TabClosedEvent -- a
            # bounded, read-only poll (same discipline every other
            # advancer's content-change wait already uses) rather than a
            # fixed sleep, since the real close is typically near-
            # instant and a fixed wait would either be too short
            # (flaky) or needlessly slow.
            remaining_ids, remaining_urls = await self._poll_until_target_closed(session, target_id_to_close, poll_timeout)

            if target_id_to_close in remaining_ids:
                raise RuntimeError(f"real target {target_id_to_close!r} is still present after close -- close did not take effect")
            if expected_remaining_url not in remaining_urls:
                raise ExpectedTargetMissingError(
                    f"after closing {target_id_to_close!r}, no real remaining target matches the expected "
                    f"original context {expected_remaining_url!r} -- remaining: {remaining_urls}"
                )

            return TabCloseResult(closed_target_id=target_id_to_close, remaining_target_ids=remaining_ids, remaining_urls=remaining_urls)
        finally:
            await session.stop()

    async def _poll_until_target_closed(
        self, session, target_id_to_close: str, timeout: float, poll_interval: float = 0.2
    ) -> tuple[list[str], list[str]]:
        """Bounded, read-only poll of the real, current target list until
        `target_id_to_close` genuinely disappears from it, or `timeout` is
        reached -- the real remaining state is returned either way (a
        timeout is a legitimate, reportable outcome, not silently
        retried forever)."""
        start = asyncio.get_event_loop().time()
        while True:
            targets = session.session_manager.get_all_page_targets()
            if not any(t.target_id == target_id_to_close for t in targets):
                return [t.target_id for t in targets], [t.url for t in targets]
            if asyncio.get_event_loop().time() - start >= timeout:
                return [t.target_id for t in targets], [t.url for t in targets]
            await asyncio.sleep(poll_interval)
