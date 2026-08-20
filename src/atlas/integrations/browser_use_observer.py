"""BrowserUseObserver (2026-08-06) — the first real BrowserObserver
implementation, wrapping the real, installed `browser-use` package
(0.13.7). This is the one place in the entire codebase that imports
browser-use directly — the same "credential/dependency-touching code
stays at the edge" discipline Digistore24Provider already established
for its own third-party SDK boundary.

Real, verified facts this module is built against (introspected
directly on this machine's installed browser-use==0.13.7 before
writing any code, not assumed from documentation, which disagreed with
itself across sources):
- `browser_use.BrowserSession` exposes a real, deterministic,
  LLM-free navigation API: start() / navigate_to(url) /
  get_state_as_text() / get_current_page_title() /
  get_current_page_url() / stop(). No LLM call is needed at all for
  basic raw-content observation — only the optional structured
  `extract` path needs one.
- `browser_use.llm.google.chat.ChatGoogle` wraps the real `google-genai`
  client; takes `api_key` explicitly (this module always passes it
  explicitly from the real GEMINI_API_KEY environment variable rather
  than relying on which exact env var name the underlying SDK defaults
  to — the same explicit-credential-passing style Digistore24Provider
  already uses).
- `browser_use.Agent(task, llm).run() -> AgentHistoryList` is the real,
  LLM-driven path, used here ONLY for the optional structured `extract`
  request — never for basic navigation/raw-text reading, so a plain
  observation never depends on (or costs) an LLM call.

Mirrors Digistore24Provider's real, loud-failure discipline: a real
navigation failure raises BrowserUseError, never a fabricated empty
PageObservation.

Structured extraction (2026-08-06, AI Orchestrator V1) no longer
instantiates ChatGoogle itself -- it routes through a real, injectable
AIProvider (atlas.integrations.base.AIProvider), defaulting to the
real GeminiProvider this module always used before this change. This
is the first real migration proving the orchestrator's actual claim:
the AI backend can be swapped (e.g. to ClaudeProvider) without any
change to this module's own code, only to which provider is passed
in.

Screenshot Reading (2026-08-09, Vision V1): `observe(..., include_
screenshot=True)` is purely additive -- every existing caller/test
that doesn't pass it keeps the exact original behavior. Uses
BrowserSession's own real `take_screenshot()` (CDP-backed, already
installed, zero new dependency) captured from inside the same live
session `_observe_async` already opens, then understood via the same
real GeminiProvider.understand_image() ImagePlugin/ScreenReader
already established -- one shared real mechanism for every real image
source, not a fourth reimplementation.

CDP Attach (2026-08-13, M1 Marketplace Discovery Safety Wiring):
`cdp_url` is a purely additive, optional constructor parameter --
`None` by default, which is BrowserSession's own real default too
(confirmed by direct inspection of the installed browser_use==0.13.7
signature), so every existing caller that doesn't pass it gets the
exact original behavior (a fresh, local, unauthenticated session).
When set, BrowserSession attaches to an already-running browser
instead of launching a new one -- e.g. a founder-controlled, dedicated
browser profile the founder has already logged into by hand. This
module never reads a hardcoded address or any credential for this --
the real value is the caller's responsibility to source (env/config/
runtime parameter), never hardcoded here.

Page Readiness (2026-08-13, M1 Marketplace Discovery Minimum Page
Readiness): `page_ready_check`/`page_ready_timeout` are purely
additive, optional -- `None`/unused by default, every existing caller
keeps the exact original behavior. A real, live probe against
Digistore24's Affiliate Marketplace found the product list is
genuinely still loading (a real `ds-spinner`/`loader-icon` was
captured mid-render) at the moment `get_state_as_text()` is first
called after navigation -- a fixed sleep would be a guess; this is a
real, bounded, state-based wait instead. Deliberately built on the
already-public, already-tested `get_state_as_text()` primitive (a
polling loop calling it repeatedly) rather than reaching into
browser_use's internal `_navigate_and_wait`/`wait_until='networkidle'`
machinery -- `networkidle` is a real, available alternative (a
network-quiescence proxy, not the same as "the specific loading
indicator this page actually shows is gone"), left as a documented,
not-yet-needed option rather than built speculatively. No action-
capable automation (no scroll/click/input of any kind) is used to
reach readiness -- purely repeated, read-only observation of the
same already-navigated, already target-verified page.

Target re-verification (2026-08-13): `verify_target` is checked
*twice* when a readiness wait happens -- once right after navigation
(before waiting at all, so we never even wait on an unapproved page),
and again *after* the wait, against a freshly re-resolved real URL
(never the pre-wait value reused) -- a client-side redirect during the
wait must never slip through on a stale check.
"""

import asyncio
import os
from pathlib import Path
from typing import Callable

from atlas.integrations.base import AIProvider, PageObservation
from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError

DEFAULT_MODEL = "gemini-flash-latest"  # verified live 2026-08-06: gemini-2.5-flash returns a real 404 for new accounts
_SCREENSHOT_DIR = Path(".atlas/screenshots")


class BrowserUseError(Exception):
    """A real browser-use failure (navigation, extraction, or missing
    credential) — never swallowed into a fabricated/partial
    observation, the same loud-failure discipline
    Digistore24APIError already establishes."""


async def select_target_by_url(session, url: str) -> None:
    """Explicit CDP target selection (2026-08-13, M1; promoted to a
    module-level function 2026-08-14, M1 Autonomous Marketplace
    Discovery Loop, so DiscoveryScrollAdvancer can reuse the exact same
    fail-closed logic rather than a second copy of it). Finds the
    *existing* real page target whose real, current URL exactly matches
    `url` and explicitly switches focus to it via the real, public
    get_or_create_cdp_session(focus=True) -- the same real method
    session.start()/connect() already uses internally for its own
    (purely positional, page_targets[0]) initial focus choice.
    Fail-closed, never a guess: raises BrowserUseError on zero matches
    (no fallback to whichever target was already focused) and on more
    than one exact match (ambiguity is reported, never silently resolved
    by picking the first one)."""
    targets = session.session_manager.get_all_page_targets()
    matches = [t for t in targets if t.url == url]

    if not matches:
        raise BrowserUseError(
            f"no existing browser target found with URL {url!r} -- {len(targets)} target(s) open, none match"
        )
    if len(matches) > 1:
        raise BrowserUseError(
            f"{len(matches)} existing targets match URL {url!r} -- ambiguous, refusing to guess which one"
        )

    await session.get_or_create_cdp_session(matches[0].target_id, focus=True)


class BrowserUseObserver:
    """Real BrowserObserver implementation over the installed
    browser-use package. `name` satisfies the BrowserObserver Protocol
    structurally (duck-typed, @runtime_checkable — no explicit
    inheritance needed, the same pattern Digistore24Provider already
    uses against CommerceProvider)."""

    name = "browser_use"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        ai_provider: AIProvider | None = None,
        cdp_url: str | None = None,
    ):
        self._api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        self._model = model
        self._ai_provider = ai_provider
        self._cdp_url = cdp_url

    def observe(
        self,
        url: str,
        extract: dict[str, str] | None = None,
        include_screenshot: bool = False,
        verify_target: Callable[[str], bool] | None = None,
        page_ready_check: Callable[[str], bool] | None = None,
        page_ready_timeout: float = 10.0,
        skip_navigate_if_already_there: bool = False,
        select_existing_target: bool = False,
    ) -> PageObservation:
        """Synchronous entry point (the BrowserObserver Protocol is
        sync; browser-use is natively async) — runs the real async
        navigation via asyncio.run(), the same bridge pattern used
        anywhere a sync Protocol wraps an inherently async real
        backend. Structured extraction (if requested) runs afterward,
        back in sync land -- deliberately outside the async browser
        session block, since AIProvider.complete_structured is itself
        a sync method with its own internal asyncio.run(), which
        cannot be called from inside an already-running event loop.
        `include_screenshot=True` (default False, purely additive)
        captures a real screenshot from inside the live session and
        understands it via the same real mechanism afterward, same
        reasoning.

        `verify_target` (2026-08-13, M1 Marketplace Discovery Safety
        Wiring, optional, `None` by default -- purely additive, every
        existing caller keeps the exact original behavior) -- checked
        against the real, post-navigation URL *inside* _observe_async(),
        before page text or a screenshot is ever read (see there) -- a
        rejected target never reaches text_content/screenshot_bytes,
        extraction, or disk, not just "read then discarded" here.

        `page_ready_check`/`page_ready_timeout` (2026-08-13, M1 Minimum
        Page Readiness, optional, `None` by default -- purely additive)
        -- when `page_ready_check` is given, a bounded, read-only poll
        of `get_state_as_text()` runs after the first `verify_target`
        check and before any content is trusted, stopping the moment
        `page_ready_check(text)` is True. `verify_target` (if given) is
        re-checked afterward against a freshly re-resolved real URL --
        see _observe_async().

        `skip_navigate_if_already_there` (2026-08-13, M1 Skip-Navigation
        Fix, default `False` -- purely additive, every existing caller
        keeps the exact original behavior) -- a real, source-verified
        fact about the underlying CDP `Page.navigate()` call `navigate_
        to()` always makes: it performs a genuine navigation/reload for
        any full URL (not a same-document/#fragment navigation), even
        when the destination is identical to the current page. A live
        probe against a real, already-authenticated, already-fully-
        loaded page confirmed this was silently discarding real,
        already-rendered content on every observe() call and replacing
        it with a freshly-reloading page. When `True`, the real current
        URL is read fresh from the session *before* deciding whether to
        navigate at all -- `navigate_to()` is skipped only on an exact
        match; any other current URL falls back to the exact existing
        navigate behavior. No safety gate is bypassed by skipping
        navigation -- `verify_target`/`page_ready_check`/the second
        `verify_target` all still run identically either way, against
        the real, freshly-read current URL -- see _observe_async().

        `select_existing_target` (2026-08-13, M1 Explicit CDP Target
        Selection, default `False` -- purely additive, every existing
        caller keeps the exact original behavior) -- a real,
        source-verified fact about `BrowserSession.start()`/`connect()`:
        it focuses whichever page target happens to be `page_targets[0]`
        -- a purely positional choice (dict-iteration order), never based
        on which real tab is focused/active/matches any URL. With a
        single real tab open this happens to be correct by coincidence,
        not by design. When `True`, the real existing target whose
        current URL exactly matches `url` is found and explicitly
        focused *before* any navigate-vs-skip decision -- fail-closed,
        never a guess, on zero matches or on more than one exact match
        (ambiguity) -- see _select_target_by_url()."""
        try:
            title, real_url, text_content, screenshot_bytes = asyncio.run(
                self._observe_async(
                    url,
                    include_screenshot,
                    verify_target,
                    page_ready_check,
                    page_ready_timeout,
                    skip_navigate_if_already_there,
                    select_existing_target,
                )
            )
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise BrowserUseError(f"real browser-use failure observing {url!r}: {exc}") from exc

        structured_data = {}
        if extract:
            structured_data = self._extract_fields(url, text_content, extract)

        screenshot_path = ""
        if include_screenshot and screenshot_bytes:
            screenshot_path = self._save_screenshot(screenshot_bytes)
            structured_data = {
                **structured_data,
                "screenshot_description": self._understand_screenshot(screenshot_bytes),
            }

        return PageObservation(
            url=real_url or url,
            title=title or "",
            text_content=text_content or "",
            structured_data=structured_data,
            screenshot_path=screenshot_path,
        )

    async def _observe_async(
        self,
        url: str,
        include_screenshot: bool,
        verify_target: Callable[[str], bool] | None = None,
        page_ready_check: Callable[[str], bool] | None = None,
        page_ready_timeout: float = 10.0,
        skip_navigate_if_already_there: bool = False,
        select_existing_target: bool = False,
    ) -> tuple[str, str, str, bytes | None]:
        from browser_use import BrowserSession

        session = BrowserSession(cdp_url=self._cdp_url)
        await session.start()
        try:
            # Explicit target selection (2026-08-13, M1): runs first, before
            # any navigate-vs-skip decision below -- session.start() itself
            # focuses whichever target happens to be page_targets[0] (a
            # purely positional choice, confirmed by direct inspection of
            # the installed browser_use source; not based on focus/activity/
            # content). With multiple real tabs open, this could silently
            # operate on the wrong one. When requested, re-focuses onto the
            # one existing target whose real, current URL exactly matches
            # `url`, fail-closed on zero or more-than-one matches -- see
            # _select_target_by_url().
            if select_existing_target:
                await self._select_target_by_url(session, url)

            # Skip-navigation fix (2026-08-13, M1): read the real, current
            # URL *before* deciding whether to navigate at all -- never
            # assume the attached tab/URL are already correct. navigate_to()
            # always performs a genuine CDP Page.navigate() (a real reload)
            # for any non-fragment URL, even an identical one -- confirmed
            # by direct inspection of the installed browser_use source --
            # which was silently discarding a real, already-authenticated,
            # already-fully-loaded page on every call. Skipped only on an
            # exact match; any other current URL (including right after a
            # fresh session.start() with nothing loaded yet) falls back to
            # the existing navigate_to() behavior unchanged.
            if skip_navigate_if_already_there and await session.get_current_page_url() == url:
                pass
            else:
                await session.navigate_to(url)
            title = await session.get_current_page_title()
            real_url = await session.get_current_page_url()
            # Target verification (2026-08-13, M1 Marketplace Discovery
            # Safety Wiring) happens right here -- after the real,
            # post-navigation URL is known, but strictly *before*
            # get_state_as_text()/take_screenshot() are ever called.
            # A redirect (or an already-open, unexpected target on an
            # attached CDP session) that fails this check means the real
            # page text/screenshot are never read at all, not read and
            # then discarded by a caller-side check afterward.
            if verify_target is not None and not verify_target(real_url):
                raise BrowserUseError(
                    f"real destination after navigation is not within the approved target scope: {real_url!r} (requested {url!r})"
                )

            if page_ready_check is not None:
                await self._wait_for_page_ready(session, page_ready_check, page_ready_timeout)

                # Re-resolve, not reuse (2026-08-13, M1 Minimum Page
                # Readiness): a client-side navigation/redirect can happen
                # during the wait -- the pre-wait real_url must never stand
                # in for what's actually current now.
                real_url = await session.get_current_page_url()
                if verify_target is not None and not verify_target(real_url):
                    raise BrowserUseError(
                        f"real destination after the readiness wait is not within the approved target scope: {real_url!r} (requested {url!r})"
                    )

            text_content = await session.get_state_as_text()
            screenshot_bytes = await session.take_screenshot() if include_screenshot else None
        finally:
            await session.stop()

        return title, real_url, text_content, screenshot_bytes

    async def _select_target_by_url(self, session, url: str) -> None:
        """Thin delegator (2026-08-14) to the module-level
        select_target_by_url() -- kept as a method so every existing
        call site/test in this class is completely unaffected; the real
        logic now lives in one place, shared with
        DiscoveryScrollAdvancer."""
        await select_target_by_url(session, url)

    async def _wait_for_page_ready(
        self,
        session,
        page_ready_check: Callable[[str], bool],
        timeout: float,
        poll_interval: float = 0.5,
    ) -> None:
        """Bounded, read-only polling on the same public, already-tested
        get_state_as_text() -- never a fixed sleep. Checks the real
        condition first (so an already-ready page returns immediately,
        with zero waiting), then sleeps only if not ready yet. Raises
        BrowserUseError with a clear, honest explanation on timeout --
        never an unbounded retry, never a silent fall-through to reading
        possibly-not-ready content."""
        start = asyncio.get_event_loop().time()
        while True:
            text = await session.get_state_as_text()
            if page_ready_check(text):
                return
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                raise BrowserUseError(f"page did not become ready within {timeout}s (page_ready_check never returned True)")
            await asyncio.sleep(poll_interval)

    def _save_screenshot(self, screenshot_bytes: bytes) -> str:
        from atlas.brain.models import new_id

        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = _SCREENSHOT_DIR / f"{new_id('screenshot')}.png"
        path.write_bytes(screenshot_bytes)
        return str(path)

    def _understand_screenshot(self, screenshot_bytes: bytes) -> str:
        provider = self._ai_provider_for_images()
        prompt = "Describe what is visually shown in this real browser screenshot in detail."
        try:
            return provider.understand_image(screenshot_bytes, prompt, media_type="image/png")
        except GeminiProviderError as exc:
            raise BrowserUseError(str(exc)) from exc

    def _ai_provider_for_images(self) -> GeminiProvider:
        # Screenshot understanding needs a real understand_image() call
        # -- not yet part of the general AIProvider Protocol (only
        # GeminiProvider implements it today, deliberately not
        # generalized before a second real image-capable provider
        # exists, the same discipline this codebase already applies
        # elsewhere), so this always uses a real GeminiProvider
        # directly regardless of which self._ai_provider was injected
        # for text extraction.
        return GeminiProvider(api_key=self._api_key, model=self._model)

    def _extract_fields(self, url: str, page_text: str, extract: dict[str, str]) -> dict[str, str]:
        """The only path in this module that makes a real AI call —
        used solely to pull specific, named fields out of real,
        already-fetched page text (never to re-navigate or take any
        action). Routes through a real AIProvider (2026-08-06, AI
        Orchestrator V1) -- the real, injected `self._ai_provider` if
        one was given, else a real GeminiProvider built from this
        observer's own resolved api_key/model, preserving this
        module's exact original default behavior. Raises
        BrowserUseError on any real provider failure (missing
        credential, or any other real call failure), never returns a
        fabricated empty dict that would look like "checked, found
        nothing"."""
        provider = self._ai_provider or GeminiProvider(api_key=self._api_key, model=self._model)
        prompt = (
            f"From the following real, already-fetched page text (url: {url}), extract real information.\n\n"
            f"PAGE TEXT:\n{page_text[:8000]}"
        )
        try:
            return provider.complete_structured(prompt, extract)
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real provider failure surfaces loudly, never silently
            raise BrowserUseError(str(exc)) from exc
