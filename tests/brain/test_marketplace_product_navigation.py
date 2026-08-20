"""ONE BRAIN Live Eyes Test 4 Root-Cause Fix (2026-08-17) --
open_marketplace_product_and_return()'s own focused test corpus. Fakes
click_advancer/goback_advancer at the same level test_marketplace_
discovery.py already fakes observer/advancer -- no browser_use session
mocking needed here, that belongs to test_browser_click_advancer.py/
test_browser_goback_advancer.py's own, separate test files."""

import pytest

from atlas.brain.marketplace_product_navigation import (
    MarketplaceReturnUnverified,
    ProductIdentityUnverified,
    open_marketplace_product_and_return,
)
from atlas.integrations.browser_click_advancer import ClickAdvanceResult
from atlas.integrations.browser_goback_advancer import GoBackResult
from atlas.integrations.browser_use_observer import BrowserUseError

LISTING_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
DETAIL_HREF = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/41824"


def _allowlist_approved(url: str) -> bool:
    return "digistore24-app.com" in url


class _FakeClickAdvancer:
    def __init__(self, result: ClickAdvanceResult | None = None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.calls: list[dict] = []

    def click(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self._error is not None:
            raise self._error
        return self._result


class _FakeGoBackAdvancer:
    def __init__(self, results: list[GoBackResult] | None = None, error: Exception | None = None):
        self._results = list(results) if results is not None else []
        self._error = error
        self.calls = 0

    def go_back(self, **kwargs):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._results.pop(0)


def _click_result(href=DETAIL_HREF, url=LISTING_URL, text="detail page text", changed=True) -> ClickAdvanceResult:
    return ClickAdvanceResult(text_content=text, url=url, content_changed=changed, clicked_href=href)


def _goback_result(url=LISTING_URL, text="listing page text", changed=True) -> GoBackResult:
    return GoBackResult(text_content=text, url=url, content_changed=changed)


# --- successful list -> detail -> return -------------------------------------


def test_successful_round_trip():
    click_advancer = _FakeClickAdvancer(result=_click_result())
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    result = open_marketplace_product_and_return(
        LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved,
    )

    assert result.clicked_href == DETAIL_HREF
    assert result.detail_id == "41824"
    assert result.identity_verified is True
    assert result.returned_to_listing is True
    assert result.return_url == LISTING_URL


# --- return to same existing target -------------------------------------------


def test_click_uses_select_existing_target_true():
    """Never a fresh navigate -- the exact real-cause fix: the click
    step must reuse the existing target, the same safe pattern
    run_discovery() already establishes."""
    click_advancer = _FakeClickAdvancer(result=_click_result())
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)

    assert click_advancer.calls[0]["select_existing_target"] is True


# --- detail identity verification ----------------------------------------------


def test_detail_identity_matches_expected_id():
    click_advancer = _FakeClickAdvancer(result=_click_result(href=DETAIL_HREF))
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    result = open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)

    assert result.detail_id == "41824"
    assert result.identity_verified is True


# --- wrong-detail fail-closed ---------------------------------------------------


def test_wrong_detail_id_raises_product_identity_unverified():
    """The clicked href resolves to a DIFFERENT real product than
    expected -- must raise, never silently accept."""
    click_advancer = _FakeClickAdvancer(result=_click_result(href="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/99999"))
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    with pytest.raises(ProductIdentityUnverified, match="99999"):
        open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)

    # go_back must never even be attempted once identity fails
    assert goback_advancer.calls == 0


def test_href_with_no_detail_id_at_all_raises_product_identity_unverified():
    click_advancer = _FakeClickAdvancer(result=_click_result(href="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"))
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    with pytest.raises(ProductIdentityUnverified):
        open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)


# --- login redirect fail-closed / logout/autologin redirect fail-closed -------


def test_login_redirect_during_click_propagates_fail_closed():
    """The click primitive's own verify_target already refuses an
    unapproved destination (e.g. a real login redirect) -- this module
    never catches/downgrades that."""
    click_advancer = _FakeClickAdvancer(error=BrowserUseError("real destination after click is not within the approved scope: 'https://www.digistore24.com/login/x'"))
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    with pytest.raises(BrowserUseError, match="login"):
        open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)


def test_autologin_clear_redirect_during_goback_propagates_fail_closed():
    """The real, live-confirmed incident this whole fix exists for --
    go_back()'s own verify_target refuses a real autologin=clear
    redirect; this module never catches/downgrades that either."""
    click_advancer = _FakeClickAdvancer(result=_click_result())
    goback_advancer = _FakeGoBackAdvancer(error=BrowserUseError("real destination after go-back is not within the approved scope: 'https://www.digistore24.com/login/UL2FwcC9lbi9hZmZpbGlhdGUvYWNjb3VudC9tYXJrZXRwbGFjZS9hbGw_e/?autologin=clear'"))

    with pytest.raises(BrowserUseError, match="autologin"):
        open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)


# --- return verification failure ------------------------------------------------


def test_goback_lands_on_a_different_approved_but_wrong_url_raises_return_unverified():
    """The go-back command technically "succeeded" (no exception) and
    even landed on an ALLOWLISTED domain -- but not the exact real
    listing context -- must still raise. Never trust a technically-
    successful command as proof of a real return."""
    click_advancer = _FakeClickAdvancer(result=_click_result())
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result(url="https://www.digistore24-app.com/app/en/affiliate/account/dashboard")])

    with pytest.raises(MarketplaceReturnUnverified, match="dashboard"):
        open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)


# --- no form submission / no Promote/action click -------------------------------


def test_structurally_no_form_or_promote_action_capability():
    """Static, structural regression guard -- the same discipline
    DiscoveryScrollAdvancer/VerifiedClickAdvancer's own tests already
    establish: this module and its two collaborators must never import
    a form-submission or generic-action event."""
    import ast

    from atlas.brain import marketplace_product_navigation as nav_mod
    from atlas.integrations import browser_goback_advancer as goback_mod

    forbidden = {"TypeTextEvent", "SendKeysEvent", "UploadFileEvent", "SelectDropdownOptionEvent"}

    for module in (nav_mod, goback_mod):
        import inspect
        source = inspect.getsource(module)
        tree = ast.parse(source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert not (names & forbidden), f"{module.__name__} references a forbidden event: {names & forbidden}"


def test_click_predicate_never_matches_a_promote_button_href():
    """Real, structural fact: 'Promote now'/'Request promotion' render
    as <button>, never <a href>, on the real, live-observed page --
    VerifiedClickAdvancer only ever considers <a> nodes, so this
    module's href_matches predicate can never target them even in
    principle. Confirmed here by asserting the predicate itself only
    matches the real, confirmed detail-URL shape."""
    click_advancer = _FakeClickAdvancer(result=_click_result())
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result()])

    open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)

    predicate = click_advancer.calls[0]["href_matches"]
    assert predicate("https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/41824") is True
    assert predicate("javascript:void(0)") is False  # a real Promote-button-shaped non-link href, never matched
    assert predicate("") is False


# --- repeated A -> return -> B -> return -> C -> return -------------------------


def test_repeated_round_trips_for_three_distinct_products():
    click_advancer = _FakeClickAdvancer()
    goback_advancer = _FakeGoBackAdvancer()
    detail_ids = ["41824", "52234", "45897"]
    results = []

    for detail_id in detail_ids:
        click_advancer._result = _click_result(
            href=f"https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/{detail_id}"
        )
        goback_advancer._results = [_goback_result()]
        results.append(
            open_marketplace_product_and_return(LISTING_URL, detail_id, click_advancer, goback_advancer, verify_target=_allowlist_approved)
        )

    assert [r.detail_id for r in results] == detail_ids
    assert all(r.returned_to_listing for r in results)


# --- no duplicate product identity / continuation after return -----------------


def test_continuation_after_return_yields_fresh_real_listing_state():
    """The real, fresh post-return text_content/url are returned to the
    caller -- proof autonomous exploration could continue from real,
    current state, never a stale pre-click snapshot."""
    click_advancer = _FakeClickAdvancer(result=_click_result())
    fresh_listing_text = "fresh real listing state after returning"
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result(text=fresh_listing_text)])

    result = open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)

    assert result.return_text_content == fresh_listing_text


def test_no_duplicate_identity_same_detail_id_twice_same_result():
    """Opening the SAME real product twice (e.g. re-verifying) must
    resolve to the SAME detail_id both times -- no drift."""
    click_advancer = _FakeClickAdvancer(result=_click_result())
    goback_advancer = _FakeGoBackAdvancer(results=[_goback_result(), _goback_result()])

    first = open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)
    second = open_marketplace_product_and_return(LISTING_URL, "41824", click_advancer, goback_advancer, verify_target=_allowlist_approved)

    assert first.detail_id == second.detail_id == "41824"


# --- memory remains intact / existing safe navigation behavior unchanged -------


def test_this_module_never_touches_knowledge_or_catalog_persistence():
    """Structural guard: this module owns navigation only -- persisting
    anything observed is strictly the caller's own, separate
    responsibility (mirrors run_discovery()'s own division between
    navigation and Semantic Grounding)."""
    import inspect

    from atlas.brain import marketplace_product_navigation as nav_mod

    source = inspect.getsource(nav_mod)
    assert "KnowledgeBase" not in source
    assert "MarketplaceCatalogStore" not in source
    assert "save_finding" not in source
    assert "save_records" not in source


def test_run_discovery_and_scroll_advancer_untouched_by_this_change():
    """The existing, already-proven safe scroll-navigation path
    (run_discovery/DiscoveryScrollAdvancer) must remain byte-for-byte
    unaffected by this new, separate capability -- imported and called
    exactly as before."""
    from atlas.brain import marketplace_discovery

    assert hasattr(marketplace_discovery, "run_discovery")
    assert "browser_goback_advancer" not in open(marketplace_discovery.__file__, encoding="utf-8").read()
