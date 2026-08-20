"""M1 Marketplace Extraction Validation (2026-08-13): turns a raw
BrowserObserver text_content capture of the Digistore24 Affiliate
Marketplace list view into structured MarketplaceProductRecord objects.

Fail-closed, evidence-only, same discipline as every other extraction in
this codebase (Finding.evidence defaults to "", never fabricated): a field
is populated only when a real, structurally-anchored value was read from
the page; anything not confidently identifiable stays None, never
guessed. The exact text layout this parses was confirmed by direct,
repeated live observation (Live Validation #1-#3) -- product blocks are
anchored by real, stable component tag names (ds-marketplace-*-icon)
browser_use's DOM-to-text serializer emits, not by fragile position/
indentation matching.

Product vs. Commercial Offer semantics (2026-08-15, Architecture Review,
documentation-only -- no schema/behavior change): `MarketplaceProductRecord`
predominantly represents a real, observed Digistore24 Marketplace
commercial listing/offer -- price, commission, conversion, and earnings
are all specific to *this listing on this platform*, not universal
attributes of an underlying real-world product (confirmed directly: some
listings' own title text is itself offer/marketing copy, e.g. "Earn 60%
Commission Promoting X"). It carries a handful of product-like
attributes (`category`, loosely `product_name`) but is not, and must
never be treated as, a global/canonical Product entity. A future
`Product` entity (grouping multiple real offers for the same real-world
item, possibly across sources) is a real, distinct future concept --
deliberately not built here; see docs/BUSINESS_BRAIN_AGENTIC_OS_
SPECIFICATION.md §4.5 for the standing "shape now, implement when
evidence requires" discipline this follows.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

# Icon component tag names that precede a real per-product value line, in
# the exact order Digistore24's Marketplace card renders them (confirmed
# via Live Validation #1-#3's real captures, not guessed). Each maps to
# the raw-string field it precedes.
_ICON_FIELD_MAP = {
    "ds-marketplace-price-tag-icon": "price_raw",
    "coin-hands-icon": "commission_raw",
    "ds-marketplace-person-icon": "vendor_raw",
    "ds-marketplace-shopping-cart-icon": "cart_conversion_raw",
    "ds-marketplace-cancel-icon": "secondary_rate_raw",
    "ds-marketplace-calender-icon": "observed_date_raw",
}

# The real, structurally-confirmed markers that start a product block (the
# bookmark/favorite-star icon, always the first icon in a card). Digistore24
# renders one of TWO real tag variants depending on whether the account has
# already favorited that listing -- confirmed live (2026-08-16, Independent
# Live DOM Audit, root-cause of a real production defect): a card using the
# unrecognized variant was invisible to this parser's card-boundary
# detection, silently merging its own price/commission/vendor fields into
# the PREVIOUS recognized card and donating its name text to whichever
# recognized card came NEXT -- producing both fully-dropped cards and
# cross-wired name/vendor/price combinations between adjacent real cards
# (live-reproduced on Page 1: "The Genius Wave" card's real fields were
# recorded under "Joseph's Well"'s name; "Advanced Amino Formula" and "The
# Self-Sufficient Backyard" were dropped entirely). A small, explicit,
# evidence-only set -- not a generic icon framework, and no other variant is
# inferred beyond what was actually observed in the live DOM.
_START_MARKER_ICONS = {"ds-marketplace-bookmark-icon", "ds-marketplace-bookmark-filled-icon"}

# Known non-field text lines that must never be mistaken for the next
# product's name line -- pure UI-chrome link labels, carry no per-card
# information (see _ACTION_STATUS_TEXTS below for the four real,
# information-bearing action-button labels, deliberately NOT in this set).
_NON_FIELD_TEXT = {"Sales page", "Affiliate support page"}

# Real, live-confirmed (2026-08-16) action-button text values -- the
# literal, observed action-status signal Digistore24 shows per card.
# Captured verbatim into action_status_raw, never interpreted here (no
# ranking/weighting: "Capture != Weight," founder's explicit instruction).
# Open, non-exhaustive set -- a future, unseen value simply falls through
# to the ordinary name_candidate path unrecognized, the same fail-open-to-
# name-candidate behavior every other unrecognized text line already has.
_ACTION_STATUS_TEXTS = {"Promote now", "Request promotion", "Copy promo link", "Promo link requested"}

_TAG_PREFIX_RE = re.compile(r"^(\|[^|]*\|)?\s*\*?\[?\d*\]?<")
_TAG_NAME_RE = re.compile(r"<([a-zA-Z][\w-]*)\b")
_TAG_INDEX_RE = re.compile(r"\[(\d+)\]")
_DOLLAR_RE = re.compile(r"^\$[\d,]+\.\d{2}$")
_PERCENT_RE = re.compile(r"^\d+(\.\d+)?%\*?$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")
_DETAIL_ID_RE = re.compile(r"/marketplace/all/detail/(\d+)")


@dataclass
class MarketplaceProductRecord:
    """One real, observed Digistore24 Marketplace commercial listing/
    offer -- see this module's own docstring for the full Product-vs-
    Offer distinction (2026-08-15). Not a global/canonical Product
    entity: `price`/`commission_pct`/`cart_conversion_pct`/
    `net_earnings_per_sale`/`earnings_per_cart_visitor` describe *this
    listing*, not a universal fact about an underlying real-world item.
    Every numeric/text field is either a direct read of a real,
    structurally-anchored value or None -- never fabricated. Marketplace
    statistics recorded here are evidence inputs only; this dataclass
    makes no claim about whether the listing is good or worth promoting
    (see marketplace_evaluation.py for that, separately).

    `detail_id`/`detail_url` (2026-08-15, Marketplace Product Detail
    Identity): a provider-scoped listing identifier -- conceptually
    `(provider="digistore24", external_id=detail_id)`, never a
    global_product_id -- the real internal Digistore24 detail-page link
    (`.../marketplace/all/detail/<ID>`), when the title candidate has one
    -- live-verified as real and unique *within this platform's listings*
    (9/9 confirmed distinct across Page 2), proven robust to a corrupted
    title (Dentitox: title text is a stray URL, detail_id still valid),
    proven to be genuinely absent for some real listings (Prime Perform
    Supplement EN has no title `<a>` at all). Both `None` by default --
    every existing caller/test that doesn't supply `href_map` to
    extract_marketplace_products() keeps the exact original behavior.

    Deliberately NOT part of dedupe_key() (see marketplace_extraction.
    dedupe_key()'s own docstring) and NOT a required field -- a listing
    missing a title link is a real, confirmed case, not an extraction
    failure.

    `action_status_raw`/`commission_type_raw` (2026-08-16, Information
    Preservation -- Semantic Grounding Wiring): capture-without-
    interpretation, per the founder's explicit "Capture != Weight"
    instruction -- neither field feeds any ranking/scoring here or
    anywhere yet. `action_status_raw` is the literal, real action-button
    text observed on the card ("Promote now" / "Request promotion" /
    "Copy promo link" / "Promo link requested", confirmed live) --
    captured verbatim; what it implies about approval/access status is
    NOT asserted by this dataclass. `commission_type_raw` is a real,
    confirmed-absent field today: Digistore24's compact Marketplace card
    view never displays a per-listing commission-type value (one-time /
    recurring / rebill) -- "Commission type" was confirmed live to exist
    only as a Filter-sidebar category, never correlated to an individual
    listing in this view. Kept as a real field, always `None` today, so
    a future observation source (a detail page, or reading the applied
    filter) that DOES supply it is never lost for lack of somewhere to
    put it -- the same honest-absence precedent `earnings_per_cart_
    visitor` already established, not a guess dressed up as a value."""

    product_name: str
    category: str | None
    price: float | None
    commission_pct: float | None
    vendor: str | None
    cart_conversion_pct: float | None
    secondary_rate_pct: float | None
    observed_date_raw: str | None
    net_earnings_per_sale: float | None
    earnings_per_cart_visitor: float | None
    source_url: str
    observed_at: str
    field_notes: str
    detail_id: str | None = None
    detail_url: str | None = None
    action_status_raw: str | None = None
    commission_type_raw: str | None = None


def _is_tag_line(line: str) -> bool:
    return bool(_TAG_PREFIX_RE.match(line))


def _tag_name(line: str) -> str | None:
    match = _TAG_NAME_RE.search(line)
    return match.group(1) if match else None


def _tag_index(line: str) -> int | None:
    match = _TAG_INDEX_RE.search(line)
    return int(match.group(1)) if match else None


def _parse_dollar(raw: str | None) -> float | None:
    if raw is None or not _DOLLAR_RE.match(raw):
        return None
    return float(raw.replace("$", "").replace(",", ""))


def _parse_percent(raw: str | None) -> float | None:
    if raw is None or not _PERCENT_RE.match(raw):
        return None
    return float(raw.replace("%", "").replace("*", ""))


NET_EARNINGS_LABEL = "Net earnings/sale"  # the real, verbatim label text Digistore24 shows -- named here (2026-08-17) so marketplace_semantic_grounding.py can ground it without duplicating the literal string

_FIELD_NOTES = (
    "net_earnings_per_sale: a real, independent raw value read directly "
    "from the source (never computed as price * commission_pct -- the two "
    "numbers do not match a naive calculation, confirmed live, and that is "
    "not treated as an inconsistency). The source labels this field "
    "'Net earnings/sale' -- that label alone is real, grounded evidence of "
    "what the field is CALLED. No formula, fee/refund/upsell composition, "
    "or whether it is an average/estimate/historical figure is asserted "
    "here -- none of that has real evidence backing it, so it stays "
    "UNKNOWN, never guessed. "
    "secondary_rate_pct: the icon preceding this value is named "
    "'ds-marketplace-cancel-icon', which suggests a cancellation/refund-"
    "style rate, but no visible text label confirms this -- treat as raw, "
    "unconfirmed evidence, not a verified risk metric. "
    "earnings_per_cart_visitor: not present anywhere in this compact card "
    "view -- left unmeasured, never guessed; may exist on a per-product "
    "detail page not observed in this run. "
    "observed_date_raw: exact meaning (listing date / last-updated date / "
    "rebill date) not confirmed by a visible label. "
    "commission_type_raw: never present in this compact card view -- "
    "'Commission type' exists only as a Filter-sidebar category on "
    "Digistore24, not correlated to an individual listing here; always "
    "None today, not an extraction failure."
)


def _resolve_detail_identity(title_link_index: int | None, href_map: dict[int, str]) -> tuple[str | None, str | None]:
    """Correlates the real title-link `<a>` (already anchored to the same
    structural position extract_marketplace_products() uses for
    product_name -- see the `last_a_index` tracking there, never a
    proximity/regex-over-every-link scan) to its real href, when one
    exists. Returns (detail_id, detail_url).

    Deliberate safety decision (2026-08-15, flagged per standing
    instruction before changing semantics): when a title-link href exists
    but does NOT match the real, confirmed Digistore24 detail-page
    pattern, this returns (None, None) for BOTH fields -- not just
    detail_id. No real case of a non-matching title-link href has ever
    been observed; storing an unverified href under `detail_url` (a field
    name that implies "this is a real product detail page") would risk
    being misleading rather than merely incomplete. Matches this
    codebase's existing discipline elsewhere (e.g. secondary_rate_pct is
    flagged uncertain in field_notes, never silently trusted) -- here the
    safer choice is to omit rather than store-with-a-caveat, since there
    is no established meaning yet for "a title-position href that isn't a
    detail link."""
    if title_link_index is None:
        return None, None
    href = href_map.get(title_link_index)
    if href is None:
        return None, None
    match = _DETAIL_ID_RE.search(href)
    if not match:
        return None, None
    return match.group(1), href


def _finalize(raw: dict, href_map: dict[int, str]) -> MarketplaceProductRecord:
    name, _, category = raw["name_line"].partition(" | ")
    detail_id, detail_url = _resolve_detail_identity(raw.get("title_link_index"), href_map)
    return MarketplaceProductRecord(
        product_name=name.strip(),
        category=category.strip() or None,
        price=_parse_dollar(raw.get("price_raw")),
        commission_pct=_parse_percent(raw.get("commission_raw")),
        vendor=raw.get("vendor_raw"),
        cart_conversion_pct=_parse_percent(raw.get("cart_conversion_raw")),
        secondary_rate_pct=_parse_percent(raw.get("secondary_rate_raw")),
        observed_date_raw=raw.get("observed_date_raw"),
        net_earnings_per_sale=_parse_dollar(raw.get("net_earnings_raw")),
        earnings_per_cart_visitor=None,
        source_url=raw["source_url"],
        observed_at=raw["observed_at"],
        field_notes=_FIELD_NOTES,
        detail_id=detail_id,
        detail_url=detail_url,
        action_status_raw=raw.get("action_status_raw"),
        commission_type_raw=None,
    )


_PAGES_BELOW_RE = re.compile(r"([\d.]+) pages below")


def dedupe_key(record: MarketplaceProductRecord) -> str:
    """The identity key MarketplaceCatalogStore dedupes/persists by
    (2026-08-14, M1 Autonomous Marketplace Discovery Loop): normalized
    `(vendor, product_name)`. The most stable identity available today --
    no real external Digistore24 product ID is observable from the
    compact card text view (the "Sales page"/"Affiliate support page"
    links render as text only, no href), a documented limitation, not a
    guess dressed up as a real ID. Live-verified (Single Live Scroll
    Validation, 2026-08-14) as the right granularity: it correctly
    treated a product that temporarily left the rendered/virtualized
    window as the *same* product, not a new one, once it reappears.

    Important scope note (2026-08-15, Architecture Review): this is
    identity for THIS catalog's deduplication purposes only -- a stable
    key for "the same listing observed twice." It is not, and is never
    claimed to be, proof that two differently-keyed records are or are
    not the same real-world product; see this module's own top-of-file
    docstring for the full Product-vs-Offer distinction.

    Deliberately never `detail_id` (2026-08-15, Marketplace Product Detail
    Identity design, evaluated and rejected): `detail_id` can be genuinely
    absent (Prime Perform Supplement EN) or transiently missed by a given
    extraction pass -- a key that could compute differently across
    observations of the *same* real product is structurally unsafe for a
    cumulative catalog. `detail_id` is stored as strong corroborating
    evidence on the record (see MarketplaceCatalogStore.save_records()),
    never as part of identity itself."""
    vendor = (record.vendor or "").strip().casefold()
    name = record.product_name.strip().casefold()
    return f"{vendor}::{name}"


def scroll_pages_below(text_content: str) -> float | None:
    """Real, direct read of browser_use's own scroll-region accounting
    (`N.N pages below`, emitted verbatim in text_content for a scrollable
    container -- see dom/views.py's real scroll_info computation).
    None when no such line is present (nothing scrollable, or a page
    layout this hasn't been observed to emit the line for) -- never a
    fabricated 0.0 standing in for "unknown"."""
    match = _PAGES_BELOW_RE.search(text_content)
    return float(match.group(1)) if match else None


def extract_marketplace_products(
    text_content: str,
    source_url: str,
    observed_at: str | None = None,
    href_map: dict[int, str] | None = None,
) -> list[MarketplaceProductRecord]:
    """Parses a real BrowserObserver text_content capture of the
    Digistore24 Affiliate Marketplace list view into structured records.
    Pure function, no I/O, no fabrication: a product block only starts at
    a real `ds-marketplace-bookmark-icon` marker (confirmed structurally
    stable across three independent live captures), and every field stays
    None unless a real value was read for it. observe-only input --
    performs no navigation, no extraction beyond parsing already-captured
    text, no external call.

    `href_map` (2026-08-15, Marketplace Product Detail Identity,
    optional, `None` by default -- every existing caller keeps the exact
    original behavior): a real `{selector_index: href}` mapping built
    from a live `get_browser_state_summary().dom_state.selector_map`
    read (not built here -- this function stays a pure text parser, the
    same "credential/DOM-touching code stays at the edge" boundary this
    codebase already draws elsewhere).

    Correlation is structural, never a global scan: `last_a_index` tracks
    only the index of the *immediately preceding* `<a>` tag line, reset
    to None the instant any OTHER tag line is seen -- so a "Sales page"/
    "Affiliate support page" link earlier in the same card can never leak
    into a later product's title correlation, and an unrelated detail-
    style href elsewhere on the page (confirmed real case: a spurious
    secondary link near the page footer) is never picked up by proximity
    or by matching-the-pattern-anywhere. When the immediately-preceding
    line was not an `<a>` (confirmed real case: Prime Perform Supplement
    EN has no title `<a>` at all), `last_a_index` is None and
    detail_id/detail_url both stay None -- an honest result, not an
    extraction failure."""
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    href_map = href_map or {}
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]

    records: list[dict] = []
    current: dict | None = None
    pending_field: str | None = None
    name_candidate: str | None = None
    name_candidate_index: int | None = None
    last_a_index: int | None = None

    for line in lines:
        if _is_tag_line(line):
            tag = _tag_name(line)
            last_a_index = _tag_index(line) if tag == "a" else None
            if tag in _START_MARKER_ICONS:
                if current is not None:
                    records.append(current)
                if name_candidate is not None:
                    current = {
                        "name_line": name_candidate,
                        "source_url": source_url,
                        "observed_at": observed_at,
                        "title_link_index": name_candidate_index,
                    }
                else:
                    current = None
                name_candidate = None
                name_candidate_index = None
                pending_field = None
            elif tag in _ICON_FIELD_MAP:
                pending_field = _ICON_FIELD_MAP[tag]
            continue

        # text line
        if pending_field is not None and current is not None:
            current[pending_field] = line
            pending_field = None
            continue

        if line == NET_EARNINGS_LABEL and current is not None:
            current["net_earnings_raw"] = current.pop("_last_bare_dollar", None)
            continue

        if _DOLLAR_RE.match(line):
            if current is not None:
                current["_last_bare_dollar"] = line
            continue

        if line in _ACTION_STATUS_TEXTS:
            if current is not None:
                current["action_status_raw"] = line
            continue

        if line in _NON_FIELD_TEXT or _PERCENT_RE.match(line) or _DATE_RE.match(line):
            continue

        name_candidate = line
        name_candidate_index = last_a_index

    if current is not None:
        records.append(current)

    return [_finalize(r, href_map) for r in records]
