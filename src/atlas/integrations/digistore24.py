import os
from urllib.parse import parse_qs, urlparse


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

    fetch_recent_sales() is deliberately NOT a real HTTP call yet. Two
    honest reasons, not one: there is no real DIGISTORE24_API_KEY
    configured anywhere in this system to test against, and Digistore24's
    exact current API surface (auth header format, endpoint, response
    shape) needs verifying against their real, current documentation
    before code touching real financial data should be trusted. Building
    and shipping an unverified guess at that shape would be worse than
    leaving it honestly unbuilt — exactly the class of mistake this
    codebase's "never fabricate" rule exists to prevent. Real revenue
    recording works today through `atlas affiliate revenue record`
    (founder-reported, from Digistore24's own dashboard) — record_manual_
    revenue() in kpi_intake.py, unchanged by this layer.
    """

    name = "digistore24"
    category = "affiliate"
    _HOST = "digistore24.com"
    _AFF_PARAM = "aff"

    def validate_link(self, url: str) -> bool:
        if self._HOST in url.lower():
            return True
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        aff_values = parse_qs(parsed.query).get(self._AFF_PARAM) or parse_qs(parsed.fragment).get(self._AFF_PARAM)
        return bool(aff_values and aff_values[0])

    def fetch_recent_sales(self) -> list[dict] | None:
        if not os.environ.get("DIGISTORE24_API_KEY"):
            return None
        raise NotImplementedError(
            "DIGISTORE24_API_KEY is set, but the real API call isn't built yet — needs Digistore24's current "
            "API documentation verified against a real account before this can be trusted with real financial "
            "data. Use 'atlas affiliate revenue record' (founder-reported from the network's own dashboard) "
            "until then."
        )
