"""Registry of real web-search providers available to ATLAS."""

from atlas.integrations.base import SearchProvider
from atlas.integrations.search_providers import BraveSearchProvider, BingSearchProvider, DuckDuckGoSearchProvider

SEARCH_PROVIDERS: dict[str, SearchProvider] = {
    "brave": BraveSearchProvider(),
    "duckduckgo": DuckDuckGoSearchProvider(),
    "bing": BingSearchProvider(),
}

DEFAULT_SEARCH_PROVIDER = "brave"


def get_search_provider(name: str | None = None) -> SearchProvider:
    key = name if name is not None else DEFAULT_SEARCH_PROVIDER
    if key not in SEARCH_PROVIDERS:
        raise ValueError(
            f"unsupported search provider: {key!r} "
            f"(supported: {sorted(SEARCH_PROVIDERS)})"
        )
    return SEARCH_PROVIDERS[key]


def search_providers_in_order() -> list[SearchProvider]:
    return list(SEARCH_PROVIDERS.values())
