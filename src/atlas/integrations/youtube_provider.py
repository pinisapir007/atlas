import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode


class YouTubeAPIError(Exception):
    """A real call to the YouTube Data API v3 failed or returned
    something this integration doesn't understand — HTTP error,
    malformed JSON, or a response missing the shape every method is
    documented to share. Raised loud, never swallowed into a None/[]
    that would look identical to "no credential configured" or
    "genuinely zero results" — the same fail-closed discipline
    Digistore24Provider/GeminiProvider already establish (2026-08-08,
    first real YouTube integration)."""


class YouTubeProvider:
    """The first real, read-only YouTube Data API v3 integration.
    Public-data-only (search, video/channel metadata) — a plain API
    key is sufficient, no OAuth, matching the real, verified
    documentation (developers.google.com/youtube/registering_an_application):
    OAuth is only required for private-data or write operations
    (an owned channel's Analytics, uploading), neither of which this
    class does. ATLAS has no real YouTube channel of its own yet — a
    separate, already-documented capability gap — so this stays
    strictly a read-only research/market-signal tool.

    Real, verified quota facts (developers.google.com, checked
    2026-08-06): 10,000 free units/day; a `search` call costs 100
    units (~100 real searches/day on the free tier); a `videos`/
    `channels` detail lookup costs 1 unit.
    """

    name = "youtube"
    _BASE_URL = "https://www.googleapis.com/youtube/v3/"
    _API_KEY_ENV = "YOUTUBE_API_KEY"

    def _call(self, endpoint: str, params: dict) -> dict:
        """One real, unauthenticated-except-for-API-key GET call to
        `{_BASE_URL}{endpoint}` — the single place every YouTube Data
        API method this integration calls goes through, so URL
        construction and error handling exist exactly once. Raises
        YouTubeAPIError on any network failure, non-200 response, or
        a JSON body that isn't a dict — never returns a
        partially-understood response as if it were valid."""
        api_key = os.environ.get(self._API_KEY_ENV)
        if not api_key:
            raise YouTubeAPIError(f"{self._API_KEY_ENV} is not set — cannot make a real YouTube Data API call")

        query = urlencode({**params, "key": api_key})
        url = f"{self._BASE_URL}{endpoint}?{query}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise YouTubeAPIError(
                f"YouTube {endpoint} returned HTTP {exc.code}: {error_body[:500]} — "
                f"if this is 400/403, the API key, its restrictions, or {self._API_KEY_ENV} may be wrong"
            ) from exc
        except urllib.error.URLError as exc:
            raise YouTubeAPIError(f"YouTube {endpoint} network error: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise YouTubeAPIError(f"YouTube {endpoint} returned non-JSON body: {body[:500]}") from exc
        if not isinstance(parsed, dict):
            raise YouTubeAPIError(f"YouTube {endpoint} returned unexpected JSON shape (not an object): {parsed!r}")
        return parsed

    def search(self, query: str, max_results: int = 5) -> list[dict] | None:
        """Real call to the `search` endpoint — real, public video
        results for `query`, exactly as the API returns them (no
        renamed/remapped fields). None means no credential
        configured; any call that's attempted but fails raises
        YouTubeAPIError rather than returning None, so a real
        failure is never indistinguishable from "not configured"."""
        if not os.environ.get(self._API_KEY_ENV):
            return None
        response = self._call("search", {"part": "snippet", "q": query, "type": "video", "maxResults": max_results})
        items = response.get("items")
        if not isinstance(items, list):
            raise YouTubeAPIError(f"YouTube search response had no real 'items' list: {response!r}")
        return items

    def video_details(self, video_id: str) -> dict | None:
        """Real call to the `videos` endpoint for one real, known
        video id — statistics (views, likes, comments) and snippet
        metadata. None means no credential configured."""
        if not os.environ.get(self._API_KEY_ENV):
            return None
        response = self._call("videos", {"part": "snippet,statistics", "id": video_id})
        items = response.get("items")
        if not isinstance(items, list):
            raise YouTubeAPIError(f"YouTube videos response had no real 'items' list: {response!r}")
        return items[0] if items else None
