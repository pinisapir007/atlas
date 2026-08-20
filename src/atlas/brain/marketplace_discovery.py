"""Autonomous Marketplace Discovery Loop (2026-08-14, M1): observe ->
extract -> persist/dedupe -> DiscoveryScrollAdvancer scroll -> wait for
content change -> re-verify -> observe -> persist only new/updated ->
repeat -> stop deterministically.

Ties together four already-built, already-tested pieces without adding
new business logic of its own: BrowserUseObserver (initial observe),
extract_marketplace_products()/dedupe_key() (parsing/identity),
MarketplaceCatalogStore (cumulative persistence), DiscoveryScrollAdvancer
(the one narrow scroll action). This module's own real job is the
stop-condition/loop bookkeeping the founder specified -- see
run_discovery()'s docstring for the six stop conditions.

Never calls marketplace_evaluation.rank_marketplace_products() itself --
ranking is the caller's separate, explicit next step over the catalog
once discovery is done. Founder's principle, structurally honored, not
just documented: catalog ingestion and research-priority ranking are two
distinct stages, never fused into one automatic pipeline; this module
creates no Task/Proposal/Opportunity/Decision.
"""

import time
from dataclasses import dataclass
from typing import Callable

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_extraction import dedupe_key, extract_marketplace_products, scroll_pages_below
from atlas.brain.marketplace_semantic_grounding import extract_field_tooltips, ground_labeled_fields, ground_marketplace_fields
from atlas.integrations.browser_scroll_advancer import DiscoveryScrollAdvancer, scroll_pages_above
from atlas.integrations.browser_use_observer import BrowserUseObserver
from atlas.integrations.traversal_completion import PageCompletionTracker

# Stated, editable safety bounds -- same transparent-assumption class as
# affiliate_pipeline_advance.ASSUMED_MONTHLY_LEADS, not derived from any
# real distributional data yet.
MAX_DISCOVERY_CYCLES = 50
MAX_WALL_CLOCK_SECONDS = 600.0
CONSECUTIVE_EMPTY_CYCLES_TO_STOP = 2  # founder's explicit instruction: never conclude "done" from one empty cycle
PAGES_BELOW_END_THRESHOLD = 0.05  # near-zero, real scroll_info signal the list has no more content below
PAGES_ABOVE_ORIENTED_THRESHOLD = 0.05  # mirrors PAGES_BELOW_END_THRESHOLD's shape -- near-zero counts as "at the top"
MAX_ORIENTATION_SCROLLS = 20  # small, explicit, editable bound -- same class as MAX_DISCOVERY_CYCLES; never an infinite climb


@dataclass
class DiscoveryRunResult:
    cycles_run: int
    total_new_records: int
    stop_reason: str
    # 2026-08-16, Orientation Precondition -- real count of reverse (up)
    # scrolls performed before forward traversal began, 0 when the run
    # was already oriented (or had no real pages-above signal at all).
    # Additive, defaulted -- every existing positional/keyword construction
    # of this dataclass keeps working unchanged.
    orientation_scrolls_used: int = 0


def _not_loading(text: str) -> bool:
    return "ds-spinner" not in text and "loader-icon" not in text


def run_discovery(
    url: str,
    observer: BrowserUseObserver,
    advancer: DiscoveryScrollAdvancer,
    catalog: MarketplaceCatalogStore,
    verify_target: Callable[[str], bool],
    max_cycles: int = MAX_DISCOVERY_CYCLES,
    max_wall_clock_seconds: float = MAX_WALL_CLOCK_SECONDS,
    content_change_timeout: float = 15.0,
    page_ready_timeout: float = 15.0,
    time_fn: Callable[[], float] = time.monotonic,
    knowledge: KnowledgeBase | None = None,
    tracker: PageCompletionTracker | None = None,
    max_orientation_scrolls: int = MAX_ORIENTATION_SCROLLS,
) -> DiscoveryRunResult:
    """Runs one full autonomous discovery pass. Stops on exactly one of
    seven conditions, per the founder's explicit design:

    0. `orientation_failed` (2026-08-16, Root-Cause Fix -- Orientation
       Precondition, see below) -- the run could not reliably reach a
       known-oriented starting position before forward traversal was
       ever attempted. `cycles_run` is 0 for this stop reason (no real
       forward-traversal cycle happened), but `total_new_records` may
       still be > 0 -- real records observed during the failed climb are
       never discarded.
    1. `pages_below_indicates_end` -- real scroll_info signal (from
       scroll_pages_below()) shows near-zero content remaining below.
    2. `no_new_products` -- two consecutive cycles (not one --
       CONSECUTIVE_EMPTY_CYCLES_TO_STOP) produced zero new identity keys.
    3. `max_cycles_reached` -- MAX_DISCOVERY_CYCLES safety bound.
    4. `wall_clock_timeout` -- MAX_WALL_CLOCK_SECONDS safety bound,
       independent of any single cycle's own content_change_timeout.
    5. `content_change_timeout` -- a single scroll's bounded
       content-change wait timed out with zero real change -- a
       stronger, immediate signal than "zero new products", stops
       without waiting for a second occurrence.
    6. Target/domain mismatch -- deliberately **not** one of the
       DiscoveryRunResult stop_reason values. verify_target failing
       raises BrowserUseError from inside observer.observe()/
       advancer.advance() and propagates straight out of this function,
       uncaught -- the same loud, fail-closed discipline every other
       verify_target failure in this codebase already has. A security
       failure is never quietly turned into a normal-looking stopped
       result.

    Orientation Precondition (2026-08-16, root-cause fix -- see
    docs/M1_DESIGN_EXECUTION_PLAN.md's 2026-08-16 checkpoint): the real,
    repeated root cause behind Page 3's partial coverage was that this
    function always trusted "wherever the browser already is" as a valid
    starting position. It no longer does. Before any forward-traversal
    cycle, this function reads scroll_pages_above() on the real baseline
    text; if it reports more than PAGES_ABOVE_ORIENTED_THRESHOLD, it
    performs a bounded reverse climb -- real DiscoveryScrollAdvancer
    calls with direction="up", the same, already-tested, already-safe
    primitive traversal already uses for forward scrolling, never a new
    navigation mechanism -- re-checking scroll_pages_above() after each
    one, until it reaches near-zero (oriented), or `max_orientation_scrolls`
    is exhausted, or a single reverse scroll produces no real content
    change (can't climb further). The latter two cases stop the ENTIRE
    run with `orientation_failed` -- forward traversal is never attempted
    from an unconfirmed starting position, and this is never silently
    hidden behind a fallback that pretends orientation succeeded.
    `scroll_pages_above() is None` (no real scroll-region signal at all)
    is treated the same as "already oriented" -- there is nothing to
    climb past when no such signal exists, the same honest-uncertainty
    handling scroll_pages_below() already has for the symmetric case.
    Every record actually seen during the climb (before it succeeds or
    is abandoned) is still extracted and persisted via
    catalog.save_records() -- real evidence observed along the way is
    never thrown away just because the run hadn't reached "real"
    traversal yet.

    Completeness Wiring (2026-08-16): `tracker`, optional, `None` by
    default -- purely additive, identical to `knowledge`'s pattern. When
    given a real PageCompletionTracker, every record extracted in every
    cycle (both during orientation and during normal forward traversal)
    is fed to it via `tracker.observe(dedupe_key(record), record)` --
    real, virtualization-safe content tracking, parallel to (never a
    replacement for) MarketplaceCatalogStore's own persistence. This
    function deliberately does NOT call `tracker.resolve()` anywhere --
    no per-record inspection mechanism (e.g. detail-id correlation) is
    wired into this pass yet, so every observed record honestly stays
    "not_yet_inspected" and `tracker.is_inspection_complete()` will
    correctly report False until a real inspection mechanism is designed
    and wired in a future, separate change. `pages_below_indicates_end`
    alone is content-completeness, not page-completeness -- a caller
    that wants to know if a page is truly COMPLETE must additionally
    call `tracker.is_page_complete(content_complete=<stop_reason ==
    "pages_below_indicates_end">)` itself; this function does not decide
    that policy question on the caller's behalf.

    Persists every extracted record via catalog.save_records() every
    cycle (cumulative/union-based -- see MarketplaceCatalogStore),
    regardless of which stop condition eventually fires, so a run that
    stops early from max_cycles/timeout still keeps everything it saw.

    Semantic Grounding (2026-08-16, Blocker 1 -- Production Wiring):
    `knowledge`, optional, `None` by default -- purely additive, every
    existing caller/test that doesn't pass it keeps the exact original
    behavior (no grounding attempted, same as before this existed). When
    given a real `KnowledgeBase`, this function grounds real Marketplace
    fields ITSELF, autonomously, as a normal part of this loop -- not
    something a caller must do afterward, and not something a diagnostic
    script does on its behalf. Each cycle after the first (the baseline
    `observer.observe()` read has no DOM tree available; the first real
    `dom_root` arrives from the first `advancer.advance(include_dom=True)`
    call), if a real `dom_root` is available, `extract_field_tooltips()`
    reads whatever real tooltips are present THIS cycle and
    `ground_marketplace_fields()` persists them -- idempotent, so a
    tooltip already grounded on an earlier cycle is a cheap no-op, never
    a duplicate Finding/Claim. Fail-closed, unconditionally: if a cycle's
    `dom_root` carries no real tooltip for a field (or `dom_root` itself
    is unavailable this cycle), nothing is grounded for it -- the field
    stays honestly UNKNOWN (see `marketplace_semantic_grounding.
    field_grounding()`), never a guessed/hardcoded meaning standing in
    for a real one.

    `ground_labeled_fields()` (2026-08-17, Information Preservation) runs
    every cycle too, independent of `dom_root` -- it only needs
    `text_content`, so it can ground a visible-label-only field (e.g.
    `net_earnings_per_sale`, labeled 'Net earnings/sale') even on the
    very first, DOM-less cycle."""
    start_time = time_fn()
    consecutive_empty = 0
    total_new = 0
    cycles = 0

    observation = observer.observe(
        url,
        verify_target=verify_target,
        page_ready_check=_not_loading,
        page_ready_timeout=page_ready_timeout,
        skip_navigate_if_already_there=True,
        select_existing_target=True,
    )
    text_content = observation.text_content
    real_url = observation.url
    dom_root = None  # no DOM tree available from the baseline observe() -- the first real one arrives from advance() below

    # --- Orientation Precondition (2026-08-16, root-cause fix; content-
    # change detection + evidence-preservation fix 2026-08-16/17) --------
    # Never trust the browser's starting position. Real records seen
    # along the way are still persisted/tracked -- only forward-traversal
    # cycle counting and grounding are deferred to the main loop below.
    #
    # Real-bug fix, live-validation-caught: DiscoveryScrollAdvancer.advance()
    # returns content_changed=False, UNCONDITIONALLY, whenever no
    # content_changed callback is given -- it never infers a change on its
    # own. The orientation loop previously called advance() with no such
    # callback, so a real, successful reverse scroll was always reported
    # as "no progress" and the loop bailed out after exactly one attempt,
    # regardless of what actually happened. Fixed by building the same
    # identity-based (dedupe_key-set) content_changed predicate the main
    # forward-traversal loop below already uses -- no new heuristic, the
    # same real, production, evidence-based change detection either way.
    #
    # Evidence preservation is deliberately UNCONDITIONAL, not merely a
    # side effect of the content-changed fix above: every real scroll
    # result is extracted and preserved (catalog + tracker) BEFORE this
    # function ever decides success or failure -- Scroll -> Observe ->
    # Extract -> Preserve -> Evaluate, never Scroll -> Evaluate -> Return
    # -> lose evidence. This holds even on the path that still ends in
    # "orientation_failed" (bound exhausted, or a genuinely stuck scroll)
    # -- a failed orientation is not the same claim as "nothing real was
    # ever seen."
    # Canonical Identity (2026-08-17, Cognitive State Wiring -- Audit
    # finding: PageCompletionTracker was fed dedupe_key(record) directly
    # (raw, pre-reconciliation), while MarketplaceCatalogStore silently
    # reconciles a vendor-missing identity onto its real, existing match
    # -- the two diverged (Catalog=10, Tracker=11 on the same real page).
    # `_persist()` centralizes every real-record persistence in this
    # function through the ONE reconciliation MarketplaceCatalogStore
    # already performs, so Tracker (and, transitively, anything Tracker's
    # state feeds later) always keys off the SAME canonical identity
    # Catalog itself settled on -- never a second, independent identity.
    def _persist(batch: list) -> list[str]:
        new_keys, canonical_by_raw = catalog.save_records_with_identity(batch)
        if tracker is not None:
            for record in batch:
                tracker.observe(canonical_by_raw[dedupe_key(record)], record)
        return new_keys

    orientation_scrolls = 0
    pages_above = scroll_pages_above(text_content)
    while pages_above is not None and pages_above > PAGES_ABOVE_ORIENTED_THRESHOLD:
        records = extract_marketplace_products(text_content, real_url)
        total_new += len(_persist(records))

        if orientation_scrolls >= max_orientation_scrolls:
            return DiscoveryRunResult(cycles, total_new, "orientation_failed", orientation_scrolls)

        previous_keys = {dedupe_key(r) for r in records}

        def _orientation_content_changed(text: str, _previous=previous_keys, _url=real_url) -> bool:
            return {dedupe_key(r) for r in extract_marketplace_products(text, _url)} != _previous

        result = advancer.advance(
            url,
            verify_target=verify_target,
            direction="up",
            content_changed=_orientation_content_changed,
            content_change_timeout=content_change_timeout,
            select_existing_target=True,
        )
        orientation_scrolls += 1

        # Preserve BEFORE evaluating success/failure -- unconditional,
        # never gated on result.content_changed's own value.
        scrolled_records = extract_marketplace_products(result.text_content, result.url)
        total_new += len(_persist(scrolled_records))

        if not result.content_changed:
            # Can't climb further -- never fabricate arrival at the top.
            return DiscoveryRunResult(cycles, total_new, "orientation_failed", orientation_scrolls)

        text_content = result.text_content
        real_url = result.url
        pages_above = scroll_pages_above(text_content)
    # ----------------------------------------------------------------------

    while True:
        records = extract_marketplace_products(text_content, real_url)
        new_keys = _persist(records)
        total_new += len(new_keys)
        cycles += 1

        if knowledge is not None:
            if dom_root is not None:
                field_tooltips = extract_field_tooltips(dom_root)
                if field_tooltips:
                    ground_marketplace_fields(field_tooltips, knowledge)
            # Text-based, DOM-independent -- can run even on the first,
            # DOM-less cycle (2026-08-17, Information Preservation fix).
            ground_labeled_fields(text_content, knowledge)

        pages_below = scroll_pages_below(text_content)
        if pages_below is not None and pages_below <= PAGES_BELOW_END_THRESHOLD:
            return DiscoveryRunResult(cycles, total_new, "pages_below_indicates_end", orientation_scrolls)

        # Discovery stagnation ("no new keys recently") and traversal
        # exhaustion ("no more content below") are two DIFFERENT claims --
        # never merged (2026-08-17, Live Validation v2 external-screenshot
        # finding: real content ("Start Affiliate Marketing like a Pro")
        # remained below the fold when a real run stopped here on
        # no_new_products alone, with real, positive pages_below evidence
        # still present). `no_new_products` may only actually stop
        # traversal when there is NO real evidence more content remains
        # below (`pages_below is None`) -- real, positive evidence that
        # more content exists (`pages_below > threshold`, already
        # established above since the pages_below_indicates_end check
        # just above didn't fire) means "I haven't found anything new
        # lately" is not permitted to override "I can prove there's more
        # page left" -- consecutive_empty still tracks stagnation
        # honestly either way, it just isn't sufficient to stop on its
        # own when that positive evidence exists.
        if new_keys:
            consecutive_empty = 0
        else:
            consecutive_empty += 1
            more_content_below = pages_below is not None and pages_below > PAGES_BELOW_END_THRESHOLD
            if consecutive_empty >= CONSECUTIVE_EMPTY_CYCLES_TO_STOP and not more_content_below:
                return DiscoveryRunResult(cycles, total_new, "no_new_products", orientation_scrolls)

        if cycles >= max_cycles:
            return DiscoveryRunResult(cycles, total_new, "max_cycles_reached", orientation_scrolls)
        if time_fn() - start_time >= max_wall_clock_seconds:
            return DiscoveryRunResult(cycles, total_new, "wall_clock_timeout", orientation_scrolls)

        previous_keys = {dedupe_key(r) for r in records}

        def _content_changed(text: str, _previous=previous_keys, _url=real_url) -> bool:
            return {dedupe_key(r) for r in extract_marketplace_products(text, _url)} != _previous

        result = advancer.advance(
            url,
            verify_target=verify_target,
            content_changed=_content_changed,
            content_change_timeout=content_change_timeout,
            select_existing_target=True,
            include_dom=knowledge is not None,
        )

        if not result.content_changed:
            # Preserve BEFORE returning -- this exact path (real scroll,
            # then immediate return) previously discarded
            # result.text_content's records silently. Deliberately NOT
            # done unconditionally on the continue-path below: this
            # function's own `new_keys` freshness signal (consecutive_empty
            # / no_new_products, above) depends on catalog.save_records()
            # genuinely returning "new" the first time a key is saved --
            # pre-saving here on every cycle would make the next
            # iteration's own top-of-loop save look falsely stale. Saving
            # only on the return path avoids that, while still closing
            # the real evidence-loss gap (nothing is lost on a return,
            # nothing is double-counted on a continue).
            scrolled_records = extract_marketplace_products(result.text_content, result.url)
            total_new += len(_persist(scrolled_records))
            return DiscoveryRunResult(cycles, total_new, "content_change_timeout", orientation_scrolls)

        text_content = result.text_content
        real_url = result.url
        dom_root = result.dom_root
