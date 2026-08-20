from pathlib import Path

from atlas.brain.marketplace_extraction import MarketplaceProductRecord, dedupe_key, extract_marketplace_products, scroll_pages_below

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "browser_snapshots" / "digistore24_marketplace_sample.txt"
SOURCE_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"
OBSERVED_AT = "2026-08-13T12:00:00+00:00"


def _real_snapshot_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_extracts_every_real_product_card_from_a_live_captured_snapshot():
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)

    assert len(records) >= 4
    names = [r.product_name for r in records]
    assert "Joseph’s Well – Blockbuster Offer From Top Diamond Vendor" in names
    assert "The Genius Wave" in names


def test_first_record_has_every_confidently_readable_field_populated():
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)
    first = records[0]

    assert first.product_name == "Joseph’s Well – Blockbuster Offer From Top Diamond Vendor"
    assert first.category == "Book (printed)"
    assert first.price == 83.67
    assert first.commission_pct == 75.0
    assert first.vendor == "megadrought"
    assert first.cart_conversion_pct == 16.0
    assert first.secondary_rate_pct == 5.41
    assert first.observed_date_raw == "8/19/25"
    assert first.net_earnings_per_sale == 75.35
    assert first.source_url == SOURCE_URL
    assert first.observed_at == OBSERVED_AT


def test_second_record_is_parsed_independently_of_the_first():
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)
    second = records[1]

    assert second.product_name == "Earn 60% Commission Promoting Advanced Amino Formula"
    assert second.category == "Supplements - health"
    assert second.price == 122.88
    assert second.commission_pct == 60.0
    assert second.vendor == "soundview"
    assert second.net_earnings_per_sale == 69.33


def test_earnings_per_cart_visitor_is_never_fabricated():
    """This field is not present anywhere in the real captured page --
    every record must report it as None, never a guessed value."""
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)

    assert all(r.earnings_per_cart_visitor is None for r in records)


def test_secondary_rate_field_notes_disclose_the_real_uncertainty():
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)

    assert "not confirmed" in records[0].field_notes
    assert "cancellation/refund" in records[0].field_notes


def test_no_products_in_text_with_no_bookmark_icon_markers_returns_empty_list():
    records = extract_marketplace_products("just some navigation text\nDashboard\nMarketplace\n", SOURCE_URL, OBSERVED_AT)

    assert records == []


def test_default_observed_at_is_generated_when_not_provided():
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL)

    assert records[0].observed_at  # a real ISO timestamp was generated, not left blank
    assert records[0].observed_at != OBSERVED_AT


# --- Filled-bookmark start-marker variant (2026-08-16) -------------------
# Real, live-captured root cause (Independent Live DOM Audit): a card using
# the "already favorited" bookmark icon variant was invisible to card-
# boundary detection, silently merging its fields into the PREVIOUS
# recognized card and donating its name to the NEXT one.


def _card_block(
    name: str, category: str, price: str, commission: str, vendor: str, bookmark_tag: str, action_status: str | None = None
) -> str:
    """Minimal, self-contained product-card text block, same real line
    shape as tests/fixtures/browser_snapshots/digistore24_marketplace_sample.txt
    (lines 158-176), parametrized only by the bookmark tag variant.
    `action_status` (2026-08-16, optional, `None` by default -- every
    existing call keeps the exact original block) appends a real action-
    button text line at the end of the card, the same real position
    confirmed live (right before the next card's name line)."""
    block = (
        f"{name} | {category}\n"
        f"[1]<div />\n"
        f"\t[2]<ds-marketplace-icon />\n"
        f"\t\t[3]<{bookmark_tag} />\n"
        f"\t\t\t[4]<svg /> <!-- SVG content collapsed -->\n"
        f"[5]<ds-marketplace-icon />\n"
        f"\t[6]<ds-marketplace-price-tag-icon />\n"
        f"\t\t<svg /> <!-- SVG content collapsed -->\n"
        f"[7]<p />\n"
        f"\t${price}\n"
        f"[8]<ds-icon />\n"
        f"\t[9]<coin-hands-icon />\n"
        f"\t\t<svg /> <!-- SVG content collapsed -->\n"
        f"[10]<span />\n"
        f"\t{commission}%\n"
        f"[11]<ds-marketplace-icon />\n"
        f"\t[12]<ds-marketplace-person-icon />\n"
        f"\t\t<svg /> <!-- SVG content collapsed -->\n"
        f"{vendor}\n"
    )
    if action_status is not None:
        block += f"{action_status}\n"
    return block


def test_normal_bookmark_icon_card_still_extracts_correctly():
    text = _card_block("Normal Product", "Downloads", "50.00", "75.00", "normalvendor", "ds-marketplace-bookmark-icon")
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 1
    assert records[0].product_name == "Normal Product"
    assert records[0].vendor == "normalvendor"
    assert records[0].price == 50.00
    assert records[0].commission_pct == 75.00


def test_filled_bookmark_icon_card_extracts_correctly_as_its_own_record():
    text = _card_block("Favorited Product", "Downloads", "60.00", "70.00", "filledvendor", "ds-marketplace-bookmark-filled-icon")
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 1
    assert records[0].product_name == "Favorited Product"
    assert records[0].vendor == "filledvendor"
    assert records[0].price == 60.00
    assert records[0].commission_pct == 70.00


def test_normal_filled_normal_sequence_produces_three_correct_records_no_cross_wiring():
    text = (
        _card_block("Card A", "Downloads", "10.00", "10.00", "vendorA", "ds-marketplace-bookmark-icon")
        + _card_block("Card B", "Downloads", "20.00", "20.00", "vendorB", "ds-marketplace-bookmark-filled-icon")
        + _card_block("Card C", "Downloads", "30.00", "30.00", "vendorC", "ds-marketplace-bookmark-icon")
    )
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 3
    by_name = {r.product_name: r for r in records}
    assert set(by_name) == {"Card A", "Card B", "Card C"}
    assert by_name["Card A"].vendor == "vendorA" and by_name["Card A"].price == 10.00 and by_name["Card A"].commission_pct == 10.00
    assert by_name["Card B"].vendor == "vendorB" and by_name["Card B"].price == 20.00 and by_name["Card B"].commission_pct == 20.00
    assert by_name["Card C"].vendor == "vendorC" and by_name["Card C"].price == 30.00 and by_name["Card C"].commission_pct == 30.00


def test_filled_marker_card_between_two_normal_cards_is_not_swallowed_by_either_neighbor():
    """Real-shape regression, modeled on the live Advanced Amino/Self-
    Sufficient Backyard incident: a filled-marker card sandwiched between
    two normal cards must produce its own record, and neither neighbor may
    gain/lose fields because of it."""
    text = (
        _card_block("Left Neighbor", "Downloads", "11.00", "11.00", "leftvendor", "ds-marketplace-bookmark-icon")
        + _card_block("Middle Favorited", "Downloads", "22.00", "22.00", "middlevendor", "ds-marketplace-bookmark-filled-icon")
        + _card_block("Right Neighbor", "Downloads", "33.00", "33.00", "rightvendor", "ds-marketplace-bookmark-icon")
    )
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 3
    by_name = {r.product_name: r for r in records}
    assert by_name["Left Neighbor"].vendor == "leftvendor"
    assert by_name["Left Neighbor"].price == 11.00
    assert by_name["Middle Favorited"].vendor == "middlevendor"
    assert by_name["Middle Favorited"].price == 22.00
    assert by_name["Right Neighbor"].vendor == "rightvendor"
    assert by_name["Right Neighbor"].price == 33.00


# --- action_status_raw / commission_type_raw (2026-08-16, Information ----
# Preservation -- Capture != Weight, per the founder's explicit instruction)


def test_action_status_raw_captures_the_real_button_text_verbatim():
    text = _card_block(
        "Product A", "Downloads", "50.00", "75.00", "vendorA", "ds-marketplace-bookmark-icon", action_status="Promote now"
    )
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 1
    assert records[0].action_status_raw == "Promote now"


def test_action_status_raw_recognizes_all_four_known_real_values():
    for real_value in ("Promote now", "Request promotion", "Copy promo link", "Promo link requested"):
        text = _card_block("P", "Downloads", "10.00", "10.00", "v", "ds-marketplace-bookmark-icon", action_status=real_value)
        records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)
        assert records[0].action_status_raw == real_value


def test_action_status_text_is_never_mistaken_for_the_next_products_name():
    """The exact regression this capture must never reintroduce: the
    action-button text must not leak into name_candidate for whichever
    card comes next."""
    text = (
        _card_block("Card A", "Downloads", "10.00", "10.00", "vendorA", "ds-marketplace-bookmark-icon", action_status="Promote now")
        + _card_block("Card B", "Downloads", "20.00", "20.00", "vendorB", "ds-marketplace-bookmark-icon", action_status="Request promotion")
    )
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 2
    names = {r.product_name for r in records}
    assert names == {"Card A", "Card B"}
    assert "Promote now" not in names
    assert "Request promotion" not in names


def test_action_status_raw_is_none_when_no_action_button_text_present():
    text = _card_block("Product A", "Downloads", "50.00", "75.00", "vendorA", "ds-marketplace-bookmark-icon")
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert records[0].action_status_raw is None


def test_sales_page_and_affiliate_support_page_still_never_become_a_name_or_status():
    """Regression: these two remain pure UI-chrome (moved out of
    _NON_FIELD_TEXT's old combined set but still excluded), never
    captured as action_status_raw, never leaked into name_candidate."""
    text = (
        "Card A | Downloads\n"
        "[1]<div />\n"
        "\t[2]<ds-marketplace-icon />\n"
        "\t\t[3]<ds-marketplace-bookmark-icon />\n"
        "\t\t\t[4]<svg /> <!-- SVG content collapsed -->\n"
        "[5]<a />\n"
        "\tSales page\n"
        "[6]<a />\n"
        "\tAffiliate support page\n"
    )
    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert len(records) == 1
    assert records[0].product_name == "Card A"
    assert records[0].action_status_raw is None


# --- net_earnings_per_sale Information Independence (2026-08-17) --------


def test_net_earnings_per_sale_is_captured_as_a_real_independent_raw_value():
    """The exact value already worked before this fix -- this test locks
    it in against the real, live-captured fixture (verified again
    2026-08-17: $114.50 was correctly persisted for a different real
    product, Prime Perform Supplement EN, in production -- the earlier
    reported 'gap' was a diagnostic-script omission, not a real bug)."""
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)

    assert records[0].net_earnings_per_sale == 75.35


def test_net_earnings_per_sale_is_never_computed_from_price_times_commission():
    """Information Independence: the real fixture's own numbers do NOT
    match a naive price*commission calculation (Joseph's Well:
    $83.67 * 75% = $62.75, but the real observed net_earnings_per_sale is
    $75.35) -- the raw, independently-observed value must survive exactly
    as read, never silently 'corrected' toward the naive product, and the
    mismatch itself must never be treated as an extraction error."""
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)
    first = records[0]

    naive_calculation = round(first.price * (first.commission_pct / 100), 2)
    assert first.net_earnings_per_sale != naive_calculation
    assert first.net_earnings_per_sale == 75.35  # the real, raw, independent value survives unchanged


def test_net_earnings_per_sale_field_notes_disclose_no_formula_is_asserted():
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)

    assert "net_earnings_per_sale" in records[0].field_notes
    assert "No formula" in records[0].field_notes


def test_commission_type_raw_is_always_none_today_never_guessed():
    """Real, confirmed absence (2026-08-16 live audit): 'Commission type'
    never appears on the compact card view -- always None, honestly, not
    a fabricated value."""
    records = extract_marketplace_products(_real_snapshot_text(), SOURCE_URL, OBSERVED_AT)

    assert all(r.commission_type_raw is None for r in records)
    assert "commission_type_raw" in records[0].field_notes


def _record(**overrides) -> MarketplaceProductRecord:
    defaults = dict(
        product_name="Test Product",
        category="Downloads",
        price=50.0,
        commission_pct=75.0,
        vendor="testvendor",
        cart_conversion_pct=10.0,
        secondary_rate_pct=5.0,
        observed_date_raw="1/1/26",
        net_earnings_per_sale=40.0,
        earnings_per_cart_visitor=None,
        source_url=SOURCE_URL,
        observed_at=OBSERVED_AT,
        field_notes="",
    )
    defaults.update(overrides)
    return MarketplaceProductRecord(**defaults)


def test_dedupe_key_normalizes_vendor_and_product_name():
    a = _record(vendor="  TestVendor ", product_name=" Test Product ")
    b = _record(vendor="testvendor", product_name="test product")

    assert dedupe_key(a) == dedupe_key(b)


def test_dedupe_key_distinguishes_different_vendors():
    a = _record(vendor="vendorA", product_name="Same Name")
    b = _record(vendor="vendorB", product_name="Same Name")

    assert dedupe_key(a) != dedupe_key(b)


def test_dedupe_key_handles_missing_vendor_without_crashing():
    record = _record(vendor=None)

    assert dedupe_key(record) == "::test product"


def test_scroll_pages_below_reads_the_real_browser_use_scroll_accounting():
    text = "|scroll element|<mat-sidenav-content /> (0.0 pages above, 2.7 pages below)"

    assert scroll_pages_below(text) == 2.7


def test_scroll_pages_below_is_none_when_no_scroll_info_line_is_present():
    assert scroll_pages_below("just some plain text with no scroll info") is None


def test_scroll_pages_below_on_the_real_captured_fixture():
    assert scroll_pages_below(_real_snapshot_text()) == 2.7


# --- Marketplace Product Detail Identity (2026-08-15) --------------------


def _card(name_line: str, vendor: str, idx_start: int, title_link: bool = True) -> str:
    """One synthetic product card, matching the real, live-confirmed
    structure exactly: an optional title `<a>` immediately before the
    name line (title_link=False reproduces the real, confirmed Prime-
    Perform-Supplement-EN case -- no `<a>` at all), a bookmark-icon
    marker, and two secondary `<a>` links ("Sales page"/"Affiliate
    support page") -- included specifically so tests can prove those
    never leak into title correlation."""
    i = idx_start
    title_a = f"[{i}]<a />\n" if title_link else ""
    return f"""{title_a}{name_line}
[{i+1}]<div />
[{i+2}]<ds-marketplace-icon />
[{i+3}]<ds-marketplace-bookmark-icon />
[{i+4}]<svg />
[{i+5}]<ds-marketplace-icon />
[{i+6}]<ds-marketplace-price-tag-icon />
<svg />
$10.00
[{i+7}]<ds-icon />
[{i+8}]<coin-hands-icon />
<svg />
[{i+9}]<span />
50.00%
[{i+10}]<ds-marketplace-icon />
[{i+11}]<ds-marketplace-person-icon />
{vendor}
[{i+12}]<ds-marketplace-icon />
[{i+13}]<ds-marketplace-shopping-cart-icon />
<svg />
[{i+14}]<p />
10.00%*
[{i+15}]<ds-marketplace-icon />
[{i+16}]<ds-marketplace-cancel-icon />
<svg />
[{i+17}]<p />
5.00%*
[{i+18}]<ds-marketplace-icon />
[{i+19}]<ds-marketplace-calender-icon />
<svg />
1/1/26
[{i+20}]<a />
Sales page
[{i+21}]<a />
Affiliate support page
$40.00
Net earnings/sale
[{i+22}]<button />
Copy promo link
"""


def test_detail_id_correlates_via_the_title_link_index_when_href_map_supplied():
    text = _card("Test Product | Downloads", "testvendor", 100)
    href_map = {100: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/99999"}

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT, href_map=href_map)

    assert len(records) == 1
    assert records[0].detail_id == "99999"
    assert records[0].detail_url == href_map[100]


def test_dentitox_style_title_is_a_url_but_detail_id_stays_valid():
    """Correlation is structural (the title <a>'s index), not text-based
    -- a corrupted title (a raw URL instead of a real name) must never
    affect the real detail_id extraction, exactly as live-confirmed."""
    text = _card("https://dentitox24.com/help/affiliates.php | Supplements - health", "Dentitox", 200)
    href_map = {200: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/36459"}

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT, href_map=href_map)

    assert records[0].product_name == "https://dentitox24.com/help/affiliates.php"
    assert records[0].detail_id == "36459"


def test_prime_perform_style_missing_title_link_yields_none_not_a_failure():
    """Real, confirmed case: some listings have no title <a> at all. This
    must produce detail_id=None honestly, not raise or guess."""
    text = _card("Prime Perform Supplement EN | Supplements - health", "thankyouchoice", 300, title_link=False)

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT, href_map={301: "https://irrelevant/detail/1"})

    assert len(records) == 1
    assert records[0].detail_id is None
    assert records[0].detail_url is None


def test_secondary_links_never_leak_into_title_correlation():
    """The real, confirmed 45462 case: a card has more than one real
    detail-style href (title link + "Sales page"/"Affiliate support
    page" links). Only the title-anchored one may ever be selected."""
    text = _card("Test Product | Downloads", "testvendor", 100)
    href_map = {
        100: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/99999",
        120: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/11111",  # "Sales page" link
        121: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/22222",  # "Affiliate support page" link
    }

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT, href_map=href_map)

    assert records[0].detail_id == "99999"


def test_malformed_title_link_href_leaves_both_fields_none():
    """A title-link href that exists but does not match the real,
    confirmed Digistore24 detail-page pattern -- deliberately does not
    store the unverified href under detail_url either (see
    _resolve_detail_identity()'s docstring for the safety reasoning)."""
    text = _card("Test Product | Downloads", "testvendor", 100)
    href_map = {100: "https://www.digistore24-app.com/some/other/unrelated/path"}

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT, href_map=href_map)

    assert records[0].detail_id is None
    assert records[0].detail_url is None


def test_extraction_without_href_map_is_completely_unchanged():
    """Backward compatibility: every existing caller that doesn't pass
    href_map (the default) gets detail_id/detail_url=None, even for a
    real card that structurally has a title link."""
    text = _card("Test Product | Downloads", "testvendor", 100)

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT)

    assert records[0].detail_id is None
    assert records[0].detail_url is None


def test_two_products_each_correlate_to_their_own_title_link_independently():
    text = _card("Product A | Downloads", "vendorA", 100) + _card("Product B | Downloads", "vendorB", 200)
    href_map = {
        100: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/11111",
        200: "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/22222",
    }

    records = extract_marketplace_products(text, SOURCE_URL, OBSERVED_AT, href_map=href_map)

    assert len(records) == 2
    assert records[0].detail_id == "11111"
    assert records[1].detail_id == "22222"
