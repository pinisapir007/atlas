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
"""

import asyncio
import os

from atlas.integrations.base import AIProvider, PageObservation
from atlas.integrations.gemini_provider import GeminiProvider

DEFAULT_MODEL = "gemini-flash-latest"  # verified live 2026-08-06: gemini-2.5-flash returns a real 404 for new accounts


class BrowserUseError(Exception):
    """A real browser-use failure (navigation, extraction, or missing
    credential) — never swallowed into a fabricated/partial
    observation, the same loud-failure discipline
    Digistore24APIError already establishes."""


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
    ):
        self._api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        self._model = model
        self._ai_provider = ai_provider

    def observe(self, url: str, extract: dict[str, str] | None = None) -> PageObservation:
        """Synchronous entry point (the BrowserObserver Protocol is
        sync; browser-use is natively async) — runs the real async
        navigation via asyncio.run(), the same bridge pattern used
        anywhere a sync Protocol wraps an inherently async real
        backend. Structured extraction (if requested) runs afterward,
        back in sync land -- deliberately outside the async browser
        session block, since AIProvider.complete_structured is itself
        a sync method with its own internal asyncio.run(), which
        cannot be called from inside an already-running event loop."""
        try:
            title, real_url, text_content = asyncio.run(self._observe_async(url))
        except BrowserUseError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real browser-use/CDP failure surfaces loudly, never silently
            raise BrowserUseError(f"real browser-use failure observing {url!r}: {exc}") from exc

        structured_data = {}
        if extract:
            structured_data = self._extract_fields(url, text_content, extract)

        return PageObservation(
            url=real_url or url,
            title=title or "",
            text_content=text_content or "",
            structured_data=structured_data,
        )

    async def _observe_async(self, url: str) -> tuple[str, str, str]:
        from browser_use import BrowserSession

        session = BrowserSession()
        await session.start()
        try:
            await session.navigate_to(url)
            title = await session.get_current_page_title()
            real_url = await session.get_current_page_url()
            text_content = await session.get_state_as_text()
        finally:
            await session.stop()

        return title, real_url, text_content

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
