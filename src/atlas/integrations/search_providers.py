"""Provider-independent web search URL sources for ATLAS."""

from urllib.parse import quote_plus


class DuckDuckGoSearchProvider:
    name = "duckduckgo"

    def search_url(self, query: str) -> str:
        return f"https://duckduckgo.com/html/?q={quote_plus(query)}"


class BingSearchProvider:
    name = "bing"

    def search_url(self, query: str) -> str:
        return f"https://www.bing.com/search?q={quote_plus(query)}"


class BraveSearchProvider:
    """Structured Brave Search API provider."""

    name = "brave"

    def search(self, query: str, max_results: int = 5):
        import json
        import os
        import urllib.parse
        import urllib.request

        api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
        if not api_key:
            raise RuntimeError("BRAVE_SEARCH_API_KEY is not configured")

        count = max(1, min(int(max_results), 20))
        params = urllib.parse.urlencode({
            "q": query,
            "count": count,
        })

        request = urllib.request.Request(
            f"https://api.search.brave.com/res/v1/web/search?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())

        results = []
        for item in payload.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": str(item.get("title", "")).strip(),
                "url": str(item.get("url", "")).strip(),
                "snippet": str(item.get("description", "")).strip(),
            })

        return results
