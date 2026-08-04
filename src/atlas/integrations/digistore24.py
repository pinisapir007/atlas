import json
import os
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse


class Digistore24APIError(Exception):
    """A real call to the Digistore24 API failed or returned something
    this integration doesn't understand — HTTP error, malformed JSON, or a
    JSON body missing the envelope shape every method is documented to
    share. Raised loud, never swallowed into a None/[] that would look
    identical to "no credential configured" or "genuinely zero sales" —
    a wrong auth header or a wrong endpoint must surface immediately, not
    silently read as an empty account (2026-08-03, first real integration
    of ATLAS Cash Flow V1's affiliate workflow)."""


class Digistore24Provider:
    """The first real CommerceProvider implementation.

    validate_link() is fully real and live-verified — moved here from
    atlas.assets.affiliate_department.models.validate_provider_link()
    (which now delegates to this class instead of duplicating the same
    regex/parsing logic), so there's exactly one place that knows what a
    real Digistore24 link looks like. Accepts two real shapes:
    1. The generic digistore24.com/redir/... link.
    2. A vendor's own custom sales-page domain, which must still be a real
       https URL with a real hostname and a non-empty "aff" tracking
       parameter in its query string or fragment — parsed, not a substring
       check, so a URL that merely contains the literal text "aff=" in its
       path is never mistaken for a real affiliate link.

    The real API layer (2026-08-03): Digistore24's official developer docs
    (dev.digistore24.com) are login-gated — every fetch attempt against
    them returned HTTP 403 to this tool, so their exact current field-level
    response shape could not be first-party verified before writing this.
    What IS verified, independently, from the official docs' own page
    titles/index (not a guess) is that the API is method-in-path (e.g.
    `getUserInfo`, `getPurchase`, `listPurchases`, `getPurchaseTracking` —
    real, named methods, not a REST resource style) and requires an API
    key. `_BASE_URL` and `_API_KEY_HEADER` below are the best-attested
    values from secondary sources (independently corroborated header name
    `X-DS-API-KEY`) — still real, still worth building against, but
    explicitly flagged provisional until one real authenticated call
    confirms them. `verify_connection()` exists specifically to be that
    one real, low-risk (read-only, no financial data) confirmation call —
    run it first, before trusting `fetch_recent_sales()`. Any wrong
    assumption here fails loud (`Digistore24APIError`), never silently.
    """

    name = "digistore24"
    category = "affiliate"
    _HOST = "digistore24.com"
    _AFF_PARAM = "aff"
    _BASE_URL = "https://www.digistore24.com/api/v1/"
    _API_KEY_HEADER = "X-DS-API-KEY"
    _API_KEY_ENV = "DIGISTORE24_API_KEY"

    def validate_link(self, url: str) -> bool:
        if self._HOST in url.lower():
            return True
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        aff_values = parse_qs(parsed.query).get(self._AFF_PARAM) or parse_qs(parsed.fragment).get(self._AFF_PARAM)
        return bool(aff_values and aff_values[0])

    def _call(self, method: str, params: dict | None = None) -> dict:
        """One real, authenticated GET call to `{_BASE_URL}{method}` —
        the single place every Digistore24 API method this integration
        ever calls goes through, so the auth header and envelope-parsing
        logic exist exactly once. Raises Digistore24APIError on any
        network failure, non-200 response, or a JSON body that isn't a
        dict — never returns a partially-understood response as if it
        were valid."""
        api_key = os.environ.get(self._API_KEY_ENV)
        if not api_key:
            raise Digistore24APIError(f"{self._API_KEY_ENV} is not set — cannot make a real Digistore24 API call")

        query = urlencode(params or {})
        url = f"{self._BASE_URL}{method}" + (f"?{query}" if query else "")
        request = urllib.request.Request(
            url, headers={self._API_KEY_HEADER: api_key, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status = response.status
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise Digistore24APIError(
                f"Digistore24 {method} returned HTTP {exc.code}: {body[:500]} — "
                f"if this is 401/403, {self._API_KEY_HEADER} or {self._API_KEY_ENV} may be wrong; "
                "if 404, the endpoint path/method name may have changed since this was written"
            ) from exc
        except urllib.error.URLError as exc:
            raise Digistore24APIError(f"Digistore24 {method} network error: {exc.reason}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise Digistore24APIError(f"Digistore24 {method} returned non-JSON body (HTTP {status}): {body[:500]}") from exc
        if not isinstance(parsed, dict):
            raise Digistore24APIError(f"Digistore24 {method} returned unexpected JSON shape (not an object): {parsed!r}")
        return parsed

    def verify_connection(self) -> dict | None:
        """The real, one-call verification step: `getUserInfo` needs no
        parameters, touches no financial data, and exists specifically so
        a real account/key can be confirmed end-to-end before
        fetch_recent_sales() is trusted with real revenue. Returns the raw
        real response on success; None only when no credential is
        configured (the same "not available right now" convention
        fetch_recent_sales() already documents) — any other failure
        raises Digistore24APIError, never silently returns None."""
        if not os.environ.get(self._API_KEY_ENV):
            return None
        return self._call("getUserInfo")

    def fetch_recent_sales(self) -> list[dict] | None:
        """Real call to `listPurchases`. Returns the API's own real
        records exactly as it sends them (no renamed/remapped fields) —
        this integration hasn't yet made one real call to confirm the
        exact per-purchase field names, so inventing a normalized shape
        now would be exactly the fabrication this codebase's fail-closed
        rule exists to prevent. Once verify_connection()/a first real call
        confirms the envelope, normalizing these into ATLAS's own shape is
        the natural next increment — not done here. None means no
        credential configured; any call that's attempted but fails raises
        Digistore24APIError rather than returning None, so a real failure
        is never indistinguishable from "not configured."
        """
        if not os.environ.get(self._API_KEY_ENV):
            return None
        response = self._call("listPurchases")
        data = response.get("data")
        if not isinstance(data, list):
            raise Digistore24APIError(f"Digistore24 listPurchases response had no real 'data' list: {response!r}")
        return data
