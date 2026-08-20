from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_extraction import MarketplaceProductRecord
from atlas.brain.store import JSONFileStore


class _FakeStore:
    """In-memory BrainStore, same pattern used throughout this codebase's
    test suite for testing a *Store class without real disk I/O."""

    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


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
        source_url="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all",
        observed_at="2026-08-14T10:00:00+00:00",
        field_notes="",
    )
    defaults.update(overrides)
    return MarketplaceProductRecord(**defaults)


# --- Canonical Identity (2026-08-17, Cognitive State Wiring) ---------------


def test_save_records_returns_the_same_new_keys_as_the_old_signature():
    """save_records() stays 100% backward compatible -- same return
    shape/value as before this round, for every existing caller/test."""
    catalog = MarketplaceCatalogStore(store=_FakeStore())
    new_keys = catalog.save_records([_record(vendor="vendorx", product_name="X")])
    assert new_keys == ["vendorx::x"]


def test_canonical_by_raw_maps_raw_key_to_itself_when_no_reconciliation_needed():
    catalog = MarketplaceCatalogStore(store=_FakeStore())
    new_keys, canonical_by_raw = catalog.save_records_with_identity([_record(vendor="vendorx", product_name="X")])
    assert canonical_by_raw == {"vendorx::x": "vendorx::x"}


def test_canonical_by_raw_maps_vendor_missing_record_onto_the_real_reconciled_identity():
    """The exact live-audit finding: '::unlock earnings...' must map to
    'nutraville::unlock earnings...', not stay a second identity."""
    catalog = MarketplaceCatalogStore(store=_FakeStore())
    catalog.save_records([_record(vendor="Nutraville", product_name="Unlock Earnings! Promote PinealXT!")])

    _new_keys, canonical_by_raw = catalog.save_records_with_identity(
        [_record(vendor="", product_name="Unlock Earnings! Promote PinealXT!")]
    )

    raw_key = "::unlock earnings! promote pinealxt!"
    assert canonical_by_raw[raw_key] == "nutraville::unlock earnings! promote pinealxt!"
    assert catalog.known_keys() == {"nutraville::unlock earnings! promote pinealxt!"}  # never a second identity


def test_canonical_by_raw_reflects_upgrade_migration_direction_too():
    """Mirror case: placeholder observed first, real vendor arrives
    later -- the LATER record's raw key IS the canonical key (the
    placeholder gets migrated onto it, not the other way around)."""
    catalog = MarketplaceCatalogStore(store=_FakeStore())
    catalog.save_records([_record(vendor="", product_name="Some Product")])  # placeholder first

    _new_keys, canonical_by_raw = catalog.save_records_with_identity(
        [_record(vendor="RealVendor", product_name="Some Product")]
    )

    assert canonical_by_raw["realvendor::some product"] == "realvendor::some product"
    assert catalog.known_keys() == {"realvendor::some product"}


def test_resolve_canonical_is_read_only_never_persists():
    catalog = MarketplaceCatalogStore(store=_FakeStore())
    catalog.save_records([_record(vendor="Nutraville", product_name="Unlock Earnings! Promote PinealXT!")])
    before = catalog.known_keys()

    resolved = catalog.resolve_canonical(_record(vendor="", product_name="Unlock Earnings! Promote PinealXT!"))

    assert resolved == "nutraville::unlock earnings! promote pinealxt!"
    assert catalog.known_keys() == before  # nothing written


def test_resolve_canonical_returns_raw_key_when_genuinely_unknown():
    catalog = MarketplaceCatalogStore(store=_FakeStore())
    resolved = catalog.resolve_canonical(_record(vendor="", product_name="Never Seen Before"))
    assert resolved == "::never seen before"  # honest -- no reconciliation possible, no guess


def test_new_record_is_persisted_with_first_and_last_observed_at_equal():
    store = MarketplaceCatalogStore(store=_FakeStore())
    new_keys = store.save_records([_record(observed_at="2026-08-14T10:00:00+00:00")])

    assert len(new_keys) == 1
    entry = list(store.all_records().values())[0]
    assert entry["first_observed_at"] == "2026-08-14T10:00:00+00:00"
    assert entry["last_observed_at"] == "2026-08-14T10:00:00+00:00"


def test_saving_the_same_record_twice_does_not_duplicate():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record()])
    second_new_keys = store.save_records([_record()])

    assert second_new_keys == []
    assert len(store.all_records()) == 1


def test_a_record_missing_from_a_later_snapshot_is_never_removed():
    """Direct consequence of the live-verified virtualized/lazy-loaded
    behavior: a product absent from one save_records() call must not be
    deleted -- it may simply have scrolled out of the rendered window."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    a = _record(product_name="Product A", vendor="vendorA")
    b = _record(product_name="Product B", vendor="vendorB")
    store.save_records([a, b])

    # Next "snapshot" only contains A -- B scrolled out of view.
    store.save_records([a])

    assert len(store.all_records()) == 2
    names = {entry["product_name"] for entry in store.all_records().values()}
    assert names == {"Product A", "Product B"}


def test_a_record_seen_again_with_new_metrics_updates_in_place_not_duplicated():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(price=50.0, commission_pct=75.0, observed_at="2026-08-14T10:00:00+00:00")])
    new_keys = store.save_records([_record(price=60.0, commission_pct=80.0, observed_at="2026-08-14T11:00:00+00:00")])

    assert new_keys == []  # not a new identity -- must not be counted as new
    assert len(store.all_records()) == 1
    entry = list(store.all_records().values())[0]
    assert entry["price"] == 60.0
    assert entry["commission_pct"] == 80.0
    assert entry["first_observed_at"] == "2026-08-14T10:00:00+00:00"  # preserved
    assert entry["last_observed_at"] == "2026-08-14T11:00:00+00:00"  # updated


def test_different_vendor_same_product_name_are_distinct_entries():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="Shared Name", vendor="vendorA")])
    new_keys = store.save_records([_record(product_name="Shared Name", vendor="vendorB")])

    assert len(new_keys) == 1
    assert len(store.all_records()) == 2


def test_known_keys_reflects_the_persisted_catalog():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="A", vendor="vendorA"), _record(product_name="B", vendor="vendorB")])

    assert store.known_keys() == {"vendora::a", "vendorb::b"}


def test_default_path_uses_a_real_json_file_store():
    store = MarketplaceCatalogStore()
    assert isinstance(store._store, JSONFileStore)


# --- Marketplace Product Detail Identity (2026-08-15) --------------------


def test_record_with_detail_id_persists_round_trip():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(detail_id="36459", detail_url="https://real/detail/36459")])

    entry = list(store.all_records().values())[0]
    assert entry["detail_id"] == "36459"
    assert entry["detail_url"] == "https://real/detail/36459"


def test_legacy_record_without_detail_id_persists_as_none():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record()])

    entry = list(store.all_records().values())[0]
    assert entry["detail_id"] is None
    assert entry["detail_url"] is None


def test_no_id_then_later_id_upgrades_the_same_record_no_duplicate():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(observed_at="2026-08-14T10:00:00+00:00")])  # no detail_id yet
    new_keys = store.save_records(
        [_record(detail_id="36459", detail_url="https://real/detail/36459", observed_at="2026-08-14T11:00:00+00:00")]
    )

    assert new_keys == []  # same identity -- not counted as new
    assert len(store.all_records()) == 1
    entry = list(store.all_records().values())[0]
    assert entry["detail_id"] == "36459"
    assert entry["detail_url"] == "https://real/detail/36459"


def test_later_observation_without_id_does_not_erase_a_previously_known_id():
    """The founder's exact scenario: real, strong identity evidence
    already learned must never be erased by a later, partial observation
    that simply didn't correlate a link this time."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(detail_id="36459", detail_url="https://real/detail/36459", observed_at="2026-08-14T10:00:00+00:00")])
    store.save_records([_record(detail_id=None, detail_url=None, observed_at="2026-08-14T11:00:00+00:00")])

    entry = list(store.all_records().values())[0]
    assert entry["detail_id"] == "36459"
    assert entry["detail_url"] == "https://real/detail/36459"
    assert entry["last_observed_at"] == "2026-08-14T11:00:00+00:00"  # other fields still refresh normally


def test_a_real_new_id_still_overwrites_an_older_one_on_refresh():
    """Every other field keeps its existing full-refresh behavior --
    confirms the detail_id/detail_url fix is "preserve on None", not
    "never update once set"."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(detail_id="11111", observed_at="2026-08-14T10:00:00+00:00")])
    store.save_records([_record(detail_id="22222", observed_at="2026-08-14T11:00:00+00:00")])

    entry = list(store.all_records().values())[0]
    assert entry["detail_id"] == "22222"


# --- Missing-vendor identity reconciliation (2026-08-15) -----------------
# Real, live-captured root cause: the same real Marketplace card was read
# with vendor="soundview" in one scroll state and vendor=None four states
# later (a transient partial-render/virtualization miss), minting a
# spurious second identity. dedupe_key() itself is unchanged; this is
# narrow, exact-name-only reconciliation at the union layer.


def test_vendor_then_missing_vendor_reconciles_to_the_single_real_match():
    """Case A: vendor learned first, then a later read misses it."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="CircO2 Nitric Oxide Booster", vendor="soundview")])
    new_keys = store.save_records([_record(product_name="CircO2 Nitric Oxide Booster", vendor=None)])

    assert new_keys == []  # reconciled onto the existing key, never counted as new
    assert len(store.all_records()) == 1
    entry = list(store.all_records().values())[0]
    assert entry["vendor"] == "soundview"  # missing data never overwrites better known data


def test_missing_vendor_then_vendor_upgrades_the_same_placeholder_in_place():
    """Mirror-image order: an empty-vendor placeholder is recorded first,
    then the real vendor is learned later -- must upgrade in place, not
    leave a permanent orphan duplicate."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="CircO2 Nitric Oxide Booster", vendor=None, observed_at="2026-08-15T10:00:00+00:00")])
    new_keys = store.save_records(
        [_record(product_name="CircO2 Nitric Oxide Booster", vendor="soundview", observed_at="2026-08-15T11:00:00+00:00")]
    )

    assert new_keys == []  # same real identity, not a genuinely new product
    assert len(store.all_records()) == 1
    entry = list(store.all_records().values())[0]
    assert entry["vendor"] == "soundview"
    assert entry["first_observed_at"] == "2026-08-15T10:00:00+00:00"  # preserved from the placeholder
    assert entry["last_observed_at"] == "2026-08-15T11:00:00+00:00"


def test_empty_string_vendor_is_treated_the_same_as_none():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="Shared Title", vendor="soundview")])
    new_keys = store.save_records([_record(product_name="Shared Title", vendor="")])

    assert new_keys == []
    assert len(store.all_records()) == 1
    assert list(store.all_records().values())[0]["vendor"] == "soundview"


def test_ambiguous_same_name_across_two_different_vendors_is_never_auto_merged():
    """Case B: two DIFFERENT real products already share the exact same
    normalized name under different vendors. A later vendor-missing read
    of that name must not guess which one it is -- fail-closed."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records(
        [
            _record(product_name="Earn 60% Commission Promoting X", vendor="soundview"),
            _record(product_name="Earn 60% Commission Promoting X", vendor="othervendor"),
        ]
    )
    assert len(store.all_records()) == 2  # unchanged existing behavior, still distinct

    new_keys = store.save_records([_record(product_name="Earn 60% Commission Promoting X", vendor=None)])

    assert len(new_keys) == 1  # a real, distinct, flagged entry -- not merged into either candidate
    assert len(store.all_records()) == 3
    ambiguous_entries = [e for e in store.all_records().values() if e.get("identity_ambiguous")]
    assert len(ambiguous_entries) == 1
    assert ambiguous_entries[0]["vendor"] in (None, "")
    # Neither pre-existing real-vendor entry was touched/merged.
    vendors = sorted(e["vendor"] for e in store.all_records().values() if e.get("vendor"))
    assert vendors == ["othervendor", "soundview"]


def test_ambiguous_placeholder_is_never_silently_auto_upgraded_by_a_later_arrival():
    """An explicit ambiguity, once flagged, must never be silently resolved
    by a later, unrelated real-vendor arrival for that same name."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records(
        [
            _record(product_name="Earn 60% Commission Promoting X", vendor="soundview"),
            _record(product_name="Earn 60% Commission Promoting X", vendor="othervendor"),
        ]
    )
    store.save_records([_record(product_name="Earn 60% Commission Promoting X", vendor=None)])
    assert len(store.all_records()) == 3

    # A third distinct real vendor now arrives with the same exact name --
    # must become its own new entry, never silently absorb the ambiguous one.
    new_keys = store.save_records([_record(product_name="Earn 60% Commission Promoting X", vendor="thirdvendor")])

    assert len(new_keys) == 1
    assert len(store.all_records()) == 4
    ambiguous_entries = [e for e in store.all_records().values() if e.get("identity_ambiguous")]
    assert len(ambiguous_entries) == 1  # still exactly one, untouched


def test_missing_vendor_with_zero_existing_matches_is_genuinely_new_not_ambiguous():
    store = MarketplaceCatalogStore(store=_FakeStore())
    new_keys = store.save_records([_record(product_name="Brand New Unseen Product", vendor=None)])

    assert len(new_keys) == 1
    entry = list(store.all_records().values())[0]
    assert entry.get("identity_ambiguous") is not True
    assert entry["vendor"] is None


# --- price/commission_pct preserve-on-None (2026-08-16) ------------------
# Real, live-captured root cause: the CircO2 Nitric Oxide Booster card's
# real vendor was correctly preserved (fixed above), but a later partial
# read still overwrote its real price/commission with None, because those
# two numeric fields weren't yet in the preserve list.


def test_known_price_then_later_none_price_preserves_the_known_value():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="CircO2", vendor="soundview", price=135.80)])
    store.save_records([_record(product_name="CircO2", vendor="soundview", price=None)])

    entry = list(store.all_records().values())[0]
    assert entry["price"] == 135.80


def test_none_price_then_later_real_price_accepts_it():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="CircO2", vendor="soundview", price=None)])
    store.save_records([_record(product_name="CircO2", vendor="soundview", price=135.80)])

    entry = list(store.all_records().values())[0]
    assert entry["price"] == 135.80


def test_known_price_then_later_different_real_price_still_refreshes():
    """Preserve-on-None must never freeze the field -- a real price change
    (e.g. the listing was genuinely repriced) must still go through."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="CircO2", vendor="soundview", price=135.80)])
    store.save_records([_record(product_name="CircO2", vendor="soundview", price=150.00)])

    entry = list(store.all_records().values())[0]
    assert entry["price"] == 150.00


def test_known_commission_then_later_none_commission_preserves_the_known_value():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="CircO2", vendor="soundview", commission_pct=60.0)])
    store.save_records([_record(product_name="CircO2", vendor="soundview", commission_pct=None)])

    entry = list(store.all_records().values())[0]
    assert entry["commission_pct"] == 60.0


def test_a_real_zero_price_is_never_mistaken_for_missing():
    """0.0 is a real, legitimate value -- must never be treated as if it
    were None (the falsy-check trap `vendor`/`detail_id`/`detail_url` don't
    have, since an empty string is never a real value for those)."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="Free Sample", vendor="vendorX", price=9.99)])
    store.save_records([_record(product_name="Free Sample", vendor="vendorX", price=0.0)])

    entry = list(store.all_records().values())[0]
    assert entry["price"] == 0.0  # the real, later 0.0 must overwrite -- it is not "missing"


def test_circo2_style_regression_vendor_and_price_and_commission_all_survive_a_partial_read():
    """The exact real incident, reproduced: full real read, then a later
    partial-render read that carries the real vendor but None price/
    commission -- every field must survive intact."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records(
        [_record(product_name="Earn 60% Commission Promoting CircO2 Nitric Oxide Booster",
                  vendor="soundview", price=135.80, commission_pct=60.0)]
    )
    new_keys = store.save_records(
        [_record(product_name="Earn 60% Commission Promoting CircO2 Nitric Oxide Booster",
                  vendor="soundview", price=None, commission_pct=None)]
    )

    assert new_keys == []
    entry = list(store.all_records().values())[0]
    assert entry["vendor"] == "soundview"
    assert entry["price"] == 135.80
    assert entry["commission_pct"] == 60.0


# --- action_status_raw preserve-on-None (2026-08-16) ---------------------


def test_known_action_status_then_later_none_preserves_the_known_value():
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="P", vendor="v", action_status_raw="Promote now")])
    store.save_records([_record(product_name="P", vendor="v", action_status_raw=None)])

    entry = list(store.all_records().values())[0]
    assert entry["action_status_raw"] == "Promote now"


def test_action_status_raw_still_refreshes_on_a_real_different_value():
    """A real status change (e.g. approval granted) must still go through
    -- preserve-on-None never freezes the field."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="P", vendor="v", action_status_raw="Request promotion")])
    store.save_records([_record(product_name="P", vendor="v", action_status_raw="Promote now")])

    entry = list(store.all_records().values())[0]
    assert entry["action_status_raw"] == "Promote now"


def test_same_detail_id_on_two_different_vendor_name_keys_both_preserved_no_merge():
    """Real, confirmed founder requirement: no automatic merge/deletion/
    arbitration when the same detail_id appears on two different
    identity keys -- both observations are kept as-is. No new anomaly-
    detection infrastructure was built for this (none existed to reuse;
    per standing instruction, none was built new this round)."""
    store = MarketplaceCatalogStore(store=_FakeStore())
    store.save_records([_record(product_name="Old Name", vendor="vendorA", detail_id="99999")])
    store.save_records([_record(product_name="New Name", vendor="vendorA", detail_id="99999")])

    assert len(store.all_records()) == 2
    detail_ids = [entry["detail_id"] for entry in store.all_records().values()]
    assert detail_ids == ["99999", "99999"]
