"""MarketplaceCatalogStore (2026-08-14, M1 Autonomous Marketplace
Discovery Loop) -- a durable, cumulative record of every real product
ever observed on an affiliate marketplace, deliberately separate from
KnowledgeBase/Finding/Opportunity (the same separation AffiliateStore
already draws against KnowledgeBase): a catalog entry is a raw,
discovered fact, never evidence-grade Finding data, and never an
Opportunity/Decision by itself. Marketplace catalog != recommendation
(founder's explicit principle, 2026-08-14) -- this store performs no
ranking, no selection, no Task/Proposal creation.

Cumulative/union-based by design, not a mirror of the latest snapshot:
Single Live Scroll Validation (2026-08-14) proved the real Marketplace
list is virtualized/lazy-loaded -- a product disappearing from one
observe() call's extracted set is expected virtual-scroll behavior, not
evidence the product was removed. A record is only ever added or
updated here, never deleted because a later snapshot didn't include it.

Identity key: marketplace_extraction.dedupe_key() -- normalized
(vendor, product_name), the most stable identity available today (no
real external product ID is observable from the compact card text view
yet -- see MarketplaceProductRecord.field_notes). Reuses the same
BrainStore/JSONFileStore atomic-write pattern as every other store in
this codebase (KnowledgeBase, DecisionLog, Ledger, ...).
"""

from dataclasses import asdict
from pathlib import Path

from atlas.brain.marketplace_extraction import MarketplaceProductRecord, dedupe_key
from atlas.brain.store import BrainStore, JSONFileStore


def _real_vendor_matches_for_name(name_norm: str, products: dict) -> list[str]:
    """Exact-match only (normalized product_name, casefold+strip) --
    deliberately no fuzzy/similarity matching. Returns every existing
    catalog key whose entry has BOTH a real (non-empty) vendor and this
    exact normalized name -- 0, 1, or >1, letting the caller decide
    reconcile / genuinely-new / ambiguous."""
    return [
        key
        for key, existing in products.items()
        if (existing.get("vendor") or "").strip()
        and existing.get("product_name", "").strip().casefold() == name_norm
    ]


class MarketplaceCatalogStore:
    def __init__(self, path: Path = Path(".atlas/marketplace_catalog.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"products": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_records(self, records: list[MarketplaceProductRecord]) -> list[str]:
        """Backward-compatible wrapper -- returns exactly what it always
        has (`new_keys`). Delegates to save_records_with_identity(), which
        performs the identical persistence; every existing caller/test
        keeps working unchanged. See save_records_with_identity() for the
        canonical-identity contract (2026-08-17, Cognitive State Wiring)."""
        new_keys, _canonical_by_raw = self.save_records_with_identity(records)
        return new_keys

    def save_records_with_identity(self, records: list[MarketplaceProductRecord]) -> tuple[list[str], dict[str, str]]:
        """Persists every record, cumulative/union-based. A new identity
        key becomes a new catalog entry (first_observed_at ==
        last_observed_at == this record's own observed_at). An existing
        key has its current mutable fields (price/commission/conversion/
        etc.) refreshed and last_observed_at updated to this record's
        observed_at -- but first_observed_at is preserved from the
        original entry, never overwritten. Never deletes anything --
        absence from `records` is never treated as evidence a product
        should be removed (see module docstring).

        Returns the identity keys that were genuinely new this call (not
        already in the catalog before this call) -- so a caller can
        implement real stop-conditions (e.g. "two consecutive cycles
        with zero new keys") without re-deriving this itself.

        `detail_id`/`detail_url` (2026-08-15, Marketplace Product Detail
        Identity): once real, strong identity evidence, it is never
        erased by a later observation that simply didn't correlate a
        link (a real, confirmed case -- Prime Perform Supplement EN has
        no title link at all; a transient virtualization-boundary miss
        is another real, confirmed case). A `None` on the incoming
        record for either field falls back to whatever the existing
        entry already has; a real, non-`None` value always refreshes it,
        same as every other mutable field. This is a narrow, targeted
        fix for these two fields only -- every other field keeps the
        existing full-refresh-from-the-latest-observation behavior; no
        general merge policy was introduced.

        Missing-vendor identity reconciliation (2026-08-15, Digital Body
        Live Validation -- real, live-captured root cause: the exact same
        real Marketplace card was observed with vendor="soundview" in one
        scroll state and vendor=None four scroll-states later, a transient
        partial-render/virtualization read that silently minted a second,
        spurious identity key -- `dedupe_key()` itself is unchanged, this
        is reconciliation at the union layer only, per standing
        instruction not to widen identity semantics system-wide):
        - A new record with vendor missing/empty, whose own literal key
          isn't already a known entry, is checked against every existing
          entry's `product_name` (normalized, exact match only -- no
          fuzzy/similarity matching was built) that DOES have a real
          vendor. Exactly one match -> reconciled onto that entry's real
          key (never creates a second identity for the same real card).
          Zero matches -> genuinely new, proceeds under its own
          empty-vendor key unchanged. More than one match -> ambiguous,
          fail-closed: never guessed which one it is, kept as its own
          entry and flagged `identity_ambiguous: True` for the caller to
          surface honestly (e.g. as PageCompletionTracker's
          `ambiguous_unresolved`), never silently merged into either
          candidate.
        - The mirror-image order (a real vendor arrives AFTER an
          empty-vendor placeholder for the same exact name was already
          recorded) is handled symmetrically: the placeholder is upgraded
          in place (same identity, first_observed_at preserved, not
          counted in `new_keys`) rather than left as a permanent orphan
          duplicate. A placeholder already flagged `identity_ambiguous`
          is never auto-upgraded this way -- an explicit ambiguity is
          never silently resolved by a later, unrelated arrival.
        - `vendor` joins `detail_id`/`detail_url` in the existing
          preserve-on-`None` merge list -- the same "missing data must
          never overwrite better known data" rule, now applied to the
          one additional field this real incident showed needs it.

        `price`/`commission_pct` preserve-on-None (2026-08-16, Digital Body
        Live Validation -- real, live-captured: the CircO2 Nitric Oxide
        Booster card kept its real, correct `vendor="soundview"` (fixed
        above) across a partial-render state, but that same partial read
        also carried `price=None`/`commission_pct=None`, and those two
        fields were NOT yet in the preserve list -- so the later, worse
        read silently overwrote the earlier, real $135.80/60.00% with
        None). These two numeric fields need an `is None` check rather
        than the falsy check `vendor`/`detail_id`/`detail_url` use,
        specifically so a real, legitimate `0.0` price/commission is never
        mistaken for "missing" -- `vendor`/`detail_id`/`detail_url` have no
        such ambiguity (an empty string is never a real value for any of
        them). A later, DIFFERENT real (non-`None`) value still refreshes
        normally -- this preserves-on-None, it does not freeze the field
        forever.

        `action_status_raw`/`commission_type_raw` (2026-08-16, Information
        Preservation) join the same falsy-preserve list as `vendor` --
        both are real string-or-None fields (no legitimate "real zero"
        ambiguity, unlike `price`/`commission_pct`), so the plain falsy
        check already used for `vendor` applies unchanged.

        Canonical Identity (2026-08-17, Cognitive State Wiring -- Audit
        finding: Catalog reconciles vendor-missing identities down to a
        single real record, e.g. '::unlock earnings! promote pinealxt!'
        reconciling onto 'nutraville::unlock earnings! promote
        pinealxt!'; every downstream cognitive consumer that computed
        dedupe_key() itself, independently, before this fix -- notably
        PageCompletionTracker -- never saw that reconciliation and
        diverged, 11 tracked identities against 10 real Catalog ones):
        also returns `canonical_by_raw`, mapping each record's raw
        (pre-reconciliation) dedupe_key() to the real key it was actually
        persisted under this call -- the exact reconciliation this method
        already performs, simply exposed rather than kept internal.
        Downstream cognitive state (PageCompletionTracker, Claim.subject_id,
        Opportunity, revisit targets) must key off the canonical value,
        never the raw one -- the raw value may still be worth keeping for
        provenance/debugging, but it is never a second, independent
        identity."""
        data = self._read()
        products = data["products"]
        new_keys: list[str] = []
        canonical_by_raw: dict[str, str] = {}

        for record in records:
            raw_key = dedupe_key(record)
            key = raw_key
            entry = asdict(record)
            vendor_present = bool((record.vendor or "").strip())
            is_upgrade_migration = False

            if key not in products:
                name_norm = record.product_name.strip().casefold()
                if not vendor_present:
                    real_vendor_matches = _real_vendor_matches_for_name(name_norm, products)
                    if len(real_vendor_matches) == 1:
                        key = real_vendor_matches[0]
                    elif len(real_vendor_matches) > 1:
                        entry["identity_ambiguous"] = True
                else:
                    placeholder_key = f"::{name_norm}"
                    placeholder_entry = products.get(placeholder_key)
                    if placeholder_entry is not None and not placeholder_entry.get("identity_ambiguous"):
                        del products[placeholder_key]
                        entry["first_observed_at"] = placeholder_entry["first_observed_at"]
                        is_upgrade_migration = True

            if key in products:
                existing = products[key]
                entry["first_observed_at"] = existing["first_observed_at"]
                for preserve_field in ("vendor", "detail_id", "detail_url", "action_status_raw", "commission_type_raw"):
                    if not entry.get(preserve_field) and existing.get(preserve_field):
                        entry[preserve_field] = existing[preserve_field]
                for preserve_field in ("price", "commission_pct"):
                    if entry.get(preserve_field) is None and existing.get(preserve_field) is not None:
                        entry[preserve_field] = existing[preserve_field]
            elif not is_upgrade_migration:
                entry["first_observed_at"] = record.observed_at
                new_keys.append(key)
            entry["last_observed_at"] = record.observed_at
            products[key] = entry
            canonical_by_raw[raw_key] = key

        self._write(data)
        return new_keys, canonical_by_raw

    def resolve_canonical(self, record: MarketplaceProductRecord) -> str:
        """Read-only lookup: what canonical key WOULD this record resolve
        to against the CURRENT catalog state, without persisting anything.
        The identity-verification primitive Revisit needs -- re-observe a
        product, resolve its canonical identity fresh, and compare
        against the expected one; a mismatch is a real, fail-closed
        signal, never assumed away. Reuses the exact same reconciliation
        rule save_records_with_identity() applies, read-only."""
        data = self._read()
        products = data["products"]
        raw_key = dedupe_key(record)
        if raw_key in products:
            return raw_key
        if not (record.vendor or "").strip():
            name_norm = record.product_name.strip().casefold()
            matches = _real_vendor_matches_for_name(name_norm, products)
            if len(matches) == 1:
                return matches[0]
        return raw_key

    def all_records(self) -> dict[str, dict]:
        """Every catalog entry, keyed by identity, as plain dicts (every
        MarketplaceProductRecord field plus first_observed_at/
        last_observed_at). Read-only -- no ranking/selection performed
        here; see marketplace_evaluation.py for that, as a separate,
        explicit later step over this catalog."""
        return dict(self._read()["products"])

    def known_keys(self) -> set[str]:
        return set(self._read()["products"].keys())
