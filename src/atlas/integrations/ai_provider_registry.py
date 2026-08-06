"""AI_PROVIDERS registry (2026-08-06, AI Orchestrator V1) — the actual
mechanism behind "ATLAS can choose which AI tool handles a task,
without touching the calling code." Two real, live-verified backends
registered from day one: Gemini (via browser-use's ChatGoogle, already
proven live against a real page) and Claude (via the real, installed
`claude` CLI, already proven live). Adding a third real backend means
one new class satisfying AIProvider plus one entry here — never
touching an existing provider or any caller, the same extension
discipline BROWSER_OBSERVERS/PROVIDERS/SIGNAL_PROVIDERS already
establish.

Task-type -> provider routing stays deliberately minimal for now: a
caller asks for a provider by name, or uses DEFAULT_AI_PROVIDER. Real,
automatic routing by task type is future work, once more than one real
task type actually exists that needs different providers — building
that now, with only one real task type (structured extraction) in the
codebase, would be exactly the premature-abstraction mistake
claude_provider.py's own original docstring already warned against.
"""

from atlas.integrations.base import AIProvider
from atlas.integrations.claude_provider import ClaudeProvider
from atlas.integrations.gemini_provider import GeminiProvider

AI_PROVIDERS: dict[str, AIProvider] = {
    "gemini": GeminiProvider(),
    "claude": ClaudeProvider(),
}

# The provider every existing real caller (e.g. BrowserObserver's
# structured extraction) used before this registry existed -- an
# explicit, editable constant, not a hardcoded choice buried in a
# caller. Changing this one line changes the default for every caller
# that doesn't explicitly ask for a named provider.
DEFAULT_AI_PROVIDER = "gemini"


def get_ai_provider(name: str | None = None) -> AIProvider:
    """Returns the real, registered AIProvider for `name`. `name=None`
    returns the real DEFAULT_AI_PROVIDER. Raises ValueError for an
    unregistered name -- the same fail-closed lookup discipline
    get_browser_observer/get_provider already establish."""
    key = name if name is not None else DEFAULT_AI_PROVIDER
    if key not in AI_PROVIDERS:
        raise ValueError(f"unsupported AI provider: {key!r} (supported: {sorted(AI_PROVIDERS)})")
    return AI_PROVIDERS[key]
