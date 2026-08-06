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

    The real API layer (2026-08-04, corrected after a real, live probe):
    Digistore24's official developer docs (dev.digistore24.com) are still
    login-gated to this tool, but the endpoint shape is now empirically
    confirmed rather than assumed — a direct, unauthenticated HTTP request
    to `https://www.digistore24.com/api/call/getUserInfo` returns a real
    JSON envelope (`{"api_version": "1.2", ..., "result": "error",
    "message": "No API key given.", "code": 2}`), and its response headers
    explicitly list `X-DS-API-KEY` in `access-control-allow-headers` —
    confirming both `_BASE_URL` and `_API_KEY_HEADER` directly against the
    real server. The original `_BASE_URL` guess (`/api/v1/`) was wrong —
    it 404s with an HTML body, which is exactly the failure this correction
    fixes. `verify_connection()` remains the real, low-risk (read-only, no
    financial data) call to confirm a real key against this corrected URL.
    """

    name = "digistore24"
    category = "affiliate"
    _HOST = "digistore24.com"
    _AFF_PARAM = "aff"
    _BASE_URL = "https://www.digistore24.com/api/call/"
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
        # Confirmed by a real, live probe (2026-08-04): Digistore24 signals
        # an API-level failure (e.g. a missing/invalid key) with HTTP 200
        # and "result": "error" in the body, not an HTTP error status --
        # the HTTPError branch above alone would miss this entirely and
        # silently hand back an error envelope as if it were real data.
        if parsed.get("result") == "error":
            raise Digistore24APIError(
                f"Digistore24 {method} returned an API-level error (code {parsed.get('code')}): {parsed.get('message')}"
            )
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
        per-purchase records exactly as it sends them (no renamed/
        remapped fields) — the exact per-purchase field names (amount,
        date, product, ...) still haven't been observed against a real
        sale (this account's real purchase history is genuinely empty,
        confirmed 2026-08-06 across its full real range), so inventing a
        normalized shape now would still be exactly the fabrication this
        codebase's fail-closed rule exists to prevent.

        The response *envelope* itself IS now real and live-verified
        (2026-08-06, first real authenticated call ever made against
        this integration): `data` is not the sales list directly — it's
        a pagination envelope (`from`, `to`, `item_count`, `page_size`,
        `page_no`, `page_count`) with the real list nested under
        `data['purchase_list']`. The original assumption that `data`
        itself was the list was a real, live-corrected bug, the same
        "guessing beats leaving it honestly unbuilt, except when the
        guess is later proven wrong by a real call" lesson `_BASE_URL`
        already taught this module once before.

        None means no credential configured; any call that's attempted
        but fails raises Digistore24APIError rather than returning None,
        so a real failure is never indistinguishable from "not
        configured."
        """
        if not os.environ.get(self._API_KEY_ENV):
            return None
        response = self._call("listPurchases")
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("purchase_list"), list):
            raise Digistore24APIError(
                f"Digistore24 listPurchases response had no real 'data.purchase_list' list: {response!r}"
            )
        return data["purchase_list"]

    def list_marketplace_entries(self, sort_by: str | None = None) -> dict | None:
        """Real, read-only PROBE call to `listMarketplaceEntries`
        (2026-08-04, Opportunity Discovery Mission #001) — returns the
        API's complete raw response exactly as sent, unmodified and
        unmapped, specifically so its real shape can be observed for the
        first time against a real account. Deliberately not unwrapped
        (unlike fetch_recent_sales()'s `data` list) because this
        endpoint's real envelope for THIS account has never been seen —
        fetch_recent_sales() only unwraps because a live probe already
        confirmed its exact shape; this one hasn't been probed live yet.

        The official OpenAPI spec describes this endpoint as retrieving
        "marketplace data for a vendor, including statistical information
        about their entries" — unconfirmed whether a real affiliate-only
        account (no products of its own) gets real entries, an empty
        list, or a permission error. `_call()`'s existing error-envelope
        detection (`result == "error"`) already raises loudly on the
        latter, so a restricted account surfaces as a clear
        Digistore24APIError, never a silent empty result standing in for
        "checked, found nothing." `sort_by` is the one parameter the
        spec documents; no other filter (category, search term) is
        documented to exist. None means no credential configured."""
        if not os.environ.get(self._API_KEY_ENV):
            return None
        params = {"sort_by": sort_by} if sort_by else None
        return self._call("listMarketplaceEntries", params)

    def get_marketplace_entry(self, entry_id: str) -> dict | None:
        """Real, read-only PROBE call to `getMarketplaceEntry` for one
        specific, already-known entry_id — same raw, unmapped,
        discovery-oriented discipline as list_marketplace_entries(): the
        real response shape for this account has never been observed, so
        this returns the complete raw response rather than guessing at a
        `data` key to unwrap. None means no credential configured."""
        if not os.environ.get(self._API_KEY_ENV):
            return None
        return self._call("getMarketplaceEntry", {"entry_id": entry_id})

    def list_product_types(self) -> dict | None:
        """Real, read-only PROBE call to `listProductTypes` — a general
        product-type/category reference list. Its official OpenAPI
        description is "Returns a list of available product types," with
        no vendor/affiliate account-scoping language — unlike
        listMarketplaceEntries, plausibly usable regardless of account
        type, though (like every method here) that's only actually
        confirmed once a real call succeeds against this account. Same
        raw, unmapped, discovery-oriented return as the marketplace
        probes. None means no credential configured."""
        if not os.environ.get(self._API_KEY_ENV):
            return None
        return self._call("listProductTypes")
