"""Marketplace Product Round-Trip Navigation (2026-08-17, Live Eyes Test
4 Root-Cause Fix) -- the missing production orchestration capability the
first live run found: LIST -> OPEN PRODUCT DETAIL -> OBSERVE -> RETURN
SAFELY -> VERIFY SAME MARKETPLACE CONTEXT -> CONTINUE. Ties together
three already-built, already-tested pieces without adding new business
logic of its own -- the exact same "orchestration only" role
marketplace_discovery.run_discovery() already plays for autonomous
scroll: VerifiedClickAdvancer (open), VerifiedGoBackAdvancer (return),
BrowserAllowlist-style verify_target (safety gate, unchanged, caller-
supplied).

Root cause of the real session loss the first live attempt produced,
confirmed by direct evidence (see browser_goback_advancer.py's own
docstring for the full trace): returning via a plain, URL-based
`observe()` call performs a real page reload, which broke this specific
site's SPA session state. The fix is architectural, not a retry: return
via real browser-history-back (GoBackEvent), never via a constructed/
guessed return URL.

Fail-closed at every real verification point (locked, per the mission
that produced this module): a technically-successful click/go-back
command is never trusted as proof of anything on its own -- every step
re-observes reality and verifies it explicitly. `ProductIdentityUnverified`
and `MarketplaceReturnUnverified` are the two new, narrow exception
types this introduces; both mean "stop here, nothing further attempted,"
never a guessed recovery.

This module never touches identity/memory/evidence-role/provenance --
it returns a plain, structured result; persisting anything it observed
(as a real Finding, a real MarketplaceProductRecord, etc.) is the
caller's own, separate, unchanged responsibility, the same division
run_discovery() already establishes between navigation and Semantic
Grounding.
"""

import re
from dataclasses import dataclass
from typing import Callable

from atlas.integrations.browser_click_advancer import VerifiedClickAdvancer
from atlas.integrations.browser_goback_advancer import VerifiedGoBackAdvancer
from atlas.integrations.browser_use_observer import BrowserUseError

# Mirrors (does not import -- a private module attribute of
# marketplace_extraction.py, and this is a trivial, stable identity-
# marker pattern, not duplicated business logic) the same real, live-
# confirmed Digistore24 detail-URL pattern already established there.
_DETAIL_ID_RE = re.compile(r"/marketplace/all/detail/(\d+)")


class ProductIdentityUnverified(ValueError):
    """Raised when the real, observed result after a click could not be
    confirmed to correspond to the specific product the caller intended
    to open -- a technically-successful click is never, by itself,
    treated as proof of which product was actually opened."""


class MarketplaceReturnUnverified(ValueError):
    """Raised when the real destination after go-back could not be
    confirmed to be the exact real Marketplace listing context the
    caller started from -- a technically-successful go-back command is
    never, by itself, treated as proof of a real return. This is the
    exact, narrow fail-closed gate that would have caught the real
    session-loss incident before it ever propagated further."""


@dataclass
class ProductRoundTripResult:
    """A full, honest record of one real round trip -- every real fact
    observed along the way, never a bare pass/fail flag."""

    clicked_href: str
    detail_id: str | None
    detail_text_content: str
    detail_content_changed: bool
    identity_verified: bool
    return_url: str
    return_text_content: str
    returned_to_listing: bool


def open_marketplace_product_and_return(
    listing_url: str,
    expected_detail_id: str,
    click_advancer: VerifiedClickAdvancer,
    goback_advancer: VerifiedGoBackAdvancer,
    verify_target: Callable[[str], bool],
    content_change_timeout: float = 15.0,
) -> ProductRoundTripResult:
    """The one, minimal production capability this module exists to add.

    A. Capture current verified Marketplace navigation context --
       `listing_url` is the caller's own, already-verified starting
       point (the same precondition run_discovery() already requires of
       its own caller); this function does not re-navigate to it first.
    B-C. Identify + open a real product-detail link -- delegates
       entirely to the existing, unmodified VerifiedClickAdvancer.click(),
       matched by the exact real href containing `expected_detail_id`
       (never a guess, never a fuzzy match) -- structurally incapable of
       matching a "Promote"/"Request promotion" control, since those are
       real <button> elements, never <a href> nodes, and
       VerifiedClickAdvancer only ever considers <a> nodes at all.
    D. Observe the resulting page -- reuses the click result's own real
       text_content/url, never a second, redundant read.
    E. Verify real product identity -- the real, clicked href (returned
       by the click primitive itself, not re-derived) must contain the
       exact real detail id the caller intended; a missing or
       mismatched id raises ProductIdentityUnverified, fail-closed,
       nothing further attempted.
    F-G. Return + re-observe -- delegates entirely to the existing,
       unmodified VerifiedGoBackAdvancer.go_back() (real browser-history
       back, never a URL-based/guessed return).
    H. Verify real Marketplace/list context after return -- the real
       post-go-back URL must exactly equal `listing_url`; anything else
       (including, critically, a real login/logout/autologin redirect --
       verify_target's own allowlist check already refuses that inside
       go_back() itself) raises MarketplaceReturnUnverified.
    I. Preserve/recover list state to continue -- the real, fresh
       post-return text_content/url are returned to the caller so
       autonomous exploration (e.g. run_discovery()) can continue from
       wherever it actually is now, never a stale, pre-click snapshot.
    J. Fail-closed throughout -- see the two exception classes above;
       neither is ever caught and silently downgraded here.
    """
    click_result = click_advancer.click(
        listing_url,
        href_matches=lambda href: expected_detail_id in href and "/marketplace/all/detail/" in href,
        verify_target=verify_target,
        content_changed=lambda text: True,  # any real post-click read is a legitimate observation; identity is verified explicitly below, never inferred from "content changed"
        content_change_timeout=content_change_timeout,
        select_existing_target=True,
    )

    match = _DETAIL_ID_RE.search(click_result.clicked_href)
    observed_detail_id = match.group(1) if match else None
    identity_verified = observed_detail_id == expected_detail_id
    if not identity_verified:
        raise ProductIdentityUnverified(
            f"clicked href {click_result.clicked_href!r} does not resolve to the expected "
            f"detail id {expected_detail_id!r} (observed: {observed_detail_id!r}) -- stopping, nothing further attempted"
        )

    goback_result = goback_advancer.go_back(
        verify_target=verify_target,
        content_changed=lambda text: True,  # the real post-go-back URL, checked explicitly below, is what determines success -- never inferred from "content changed"
        content_change_timeout=content_change_timeout,
    )

    returned_to_listing = goback_result.url == listing_url
    if not returned_to_listing:
        raise MarketplaceReturnUnverified(
            f"real destination after go-back ({goback_result.url!r}) does not exactly match the real "
            f"Marketplace listing context ({listing_url!r}) -- stopping, nothing further attempted"
        )

    return ProductRoundTripResult(
        clicked_href=click_result.clicked_href,
        detail_id=observed_detail_id,
        detail_text_content=click_result.text_content,
        detail_content_changed=click_result.content_changed,
        identity_verified=identity_verified,
        return_url=goback_result.url,
        return_text_content=goback_result.text_content,
        returned_to_listing=returned_to_listing,
    )
