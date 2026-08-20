import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_discovery import run_discovery
from atlas.integrations.browser_scroll_advancer import ScrollAdvanceResult
from atlas.integrations.browser_use_observer import BrowserUseError

URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _catalog() -> MarketplaceCatalogStore:
    return MarketplaceCatalogStore(store=_FakeStore())


def _product_block(name: str, vendor: str) -> str:
    """A minimal, real-shaped product card block extract_marketplace_products()
    can parse -- same tag-anchor structure confirmed against the real,
    live-captured fixture."""
    return f"""{name}
[1]<div />
[2]<ds-marketplace-icon />
[3]<ds-marketplace-bookmark-icon />
[4]<svg />
[5]<ds-marketplace-icon />
[6]<ds-marketplace-price-tag-icon />
[7]<p />
$10.00
[8]<ds-icon />
[9]<coin-hands-icon />
[10]<span />
50.00%
[11]<ds-marketplace-icon />
[12]<ds-marketplace-person-icon />
{vendor}
[13]<ds-marketplace-icon />
[14]<ds-marketplace-shopping-cart-icon />
5.00%
[15]<ds-marketplace-icon />
[16]<ds-marketplace-cancel-icon />
[17]<p />
1.00%
[18]<ds-marketplace-icon />
[19]<ds-marketplace-calender-icon />
1/1/26
[20]<a />
Sales page
[21]<a />
Affiliate support page
$5.00
Net earnings/sale
[22]<button />
Copy promo link
"""


def _snapshot(
    products: list[tuple[str, str]], pages_below: float | None = None, pages_above: float = 0.0
) -> str:
    text = "".join(_product_block(name, vendor) for name, vendor in products)
    if pages_below is not None:
        text += f"|scroll element|<mat-sidenav-content /> ({pages_above} pages above, {pages_below} pages below)\n"
    return text


class _FakeObservation:
    def __init__(self, url: str, text_content: str):
        self.url = url
        self.text_content = text_content


class _FakeObserver:
    def __init__(self, text_content: str, url: str = URL, raise_error: bool = False):
        self._text_content = text_content
        self._url = url
        self._raise_error = raise_error

    def observe(self, url, **kwargs):
        if self._raise_error:
            raise BrowserUseError("target mismatch on initial observe")
        return _FakeObservation(self._url, self._text_content)


class _FakeAdvancer:
    """Returns each of `texts` in sequence, one per advance() call. The
    real content_changed predicate (built by run_discovery itself) is
    applied against the returned text, exactly mirroring how the real
    DiscoveryScrollAdvancer computes ScrollAdvanceResult.content_changed
    -- not hardcoded here, so these tests exercise the real
    key-set-comparison logic, not a stand-in for it.

    `dom_roots` (2026-08-16, Blocker 1/2 wiring tests, optional -- parallel
    list to `texts`, `None` entries by default): lets a test supply a real-
    shaped fake dom_root for a given cycle, the same way the real
    DiscoveryScrollAdvancer only populates ScrollAdvanceResult.dom_root
    when include_dom=True was requested. `received_include_dom` records
    exactly what run_discovery() passed each call, for direct assertion."""

    def __init__(self, texts: list[str], url: str = URL, dom_roots: list | None = None):
        self._texts = texts
        self._url = url
        self._dom_roots = dom_roots or [None] * len(texts)
        self.call_count = 0
        self.received_include_dom: list[bool] = []

    def advance(self, url, verify_target=None, content_changed=None, include_dom=False, **kwargs):
        text = self._texts[self.call_count]
        dom_root = self._dom_roots[self.call_count]
        self.received_include_dom.append(include_dom)
        self.call_count += 1
        if verify_target is not None and not verify_target(self._url):
            raise BrowserUseError("target mismatch during scroll")
        changed = content_changed(text) if content_changed is not None else False
        return ScrollAdvanceResult(text_content=text, url=self._url, content_changed=changed, dom_root=dom_root)


def _always_true(_url: str) -> bool:
    return True


def test_scroll_cycles_producing_new_records_continue_the_loop():
    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")]))
    advancer = _FakeAdvancer(
        [
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")]),
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC"), ("D", "vendorD")]),
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC"), ("D", "vendorD")]),  # unchanged -> stop
        ]
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "content_change_timeout"
    assert result.cycles_run == 3
    assert result.total_new_records == 4  # A, B, C, D
    assert catalog.known_keys() == {"vendora::a", "vendorb::b", "vendorc::c", "vendord::d"}


def test_two_consecutive_cycles_with_zero_new_catalog_keys_stop():
    """Real content changes each scroll (so content_change_timeout is
    never the trigger), but every extracted key was already in the
    catalog from before this run started -- must take exactly two
    consecutive such cycles to stop, per the founder's explicit
    instruction, never one."""
    catalog = _catalog()
    catalog.save_records(
        [
            *_records_from_snapshot(_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC"), ("D", "vendorD")])),
        ]
    )

    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")]))
    advancer = _FakeAdvancer(
        [_snapshot([("C", "vendorC"), ("D", "vendorD")])],  # differs from {A,B} -> real content change, but both already known
    )

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "no_new_products"
    assert result.cycles_run == 2  # cycle 1: {A,B} both known (empty #1); cycle 2: {C,D} both known (empty #2) -> stop
    assert result.total_new_records == 0


def _records_from_snapshot(text: str):
    from atlas.brain.marketplace_extraction import extract_marketplace_products

    return extract_marketplace_products(text, URL)


def test_content_change_timeout_stops_immediately_without_requiring_two_cycles():
    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA")])])  # identical -> no content change
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "content_change_timeout"
    assert result.cycles_run == 1


def test_pages_below_near_zero_stops_before_any_scroll():
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=0.0))
    advancer = _FakeAdvancer([])  # must never be called
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "pages_below_indicates_end"
    assert result.cycles_run == 1
    assert advancer.call_count == 0


def test_max_cycles_bound_stops_a_never_ending_stream_of_new_products():
    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    texts = [_snapshot([(f"P{i}", f"vendor{i}") for i in range(n + 2)]) for n in range(10)]
    advancer = _FakeAdvancer(texts)
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, max_cycles=3)

    assert result.stop_reason == "max_cycles_reached"
    assert result.cycles_run == 3


def test_wall_clock_timeout_stops_a_never_ending_stream_of_new_products():
    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    texts = [_snapshot([(f"P{i}", f"vendor{i}") for i in range(n + 2)]) for n in range(10)]
    advancer = _FakeAdvancer(texts)
    catalog = _catalog()

    clock = iter([0.0, 0.0, 100.0, 100.0, 200.0, 200.0, 900.0, 900.0, 900.0, 900.0, 900.0, 900.0])

    def fake_time_fn():
        return next(clock, 900.0)

    result = run_discovery(
        URL, observer, advancer, catalog, verify_target=_always_true, max_cycles=50, max_wall_clock_seconds=500.0, time_fn=fake_time_fn
    )

    assert result.stop_reason == "wall_clock_timeout"


def test_target_mismatch_on_initial_observe_raises_fail_closed_never_swallowed():
    observer = _FakeObserver(_snapshot([("A", "vendorA")]), raise_error=True)
    advancer = _FakeAdvancer([])
    catalog = _catalog()

    with pytest.raises(BrowserUseError):
        run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)


def test_target_mismatch_during_scroll_raises_fail_closed_never_swallowed():
    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA"), ("B", "vendorB")])])
    catalog = _catalog()

    def reject_everything(_url: str) -> bool:
        return False

    with pytest.raises(BrowserUseError):
        run_discovery(URL, observer, advancer, catalog, verify_target=reject_everything)


def test_catalog_is_populated_even_when_the_run_stops_early():
    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")]))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA"), ("B", "vendorB")])])  # unchanged -> stop after cycle 1
    catalog = _catalog()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert catalog.known_keys() == {"vendora::a", "vendorb::b"}


# --- Semantic Grounding wiring (2026-08-16, Blocker 1) ----------------------


class _FakeOriginalNode:
    def __init__(self, tag_name, parent_node=None):
        self.tag_name = tag_name
        self.parent_node = parent_node


class _FakeParentNode:
    def __init__(self, attributes):
        self.attributes = attributes


class _FakeSimplifiedNode:
    def __init__(self, original_node=None, children=None):
        self.original_node = original_node
        self.children = children or []


def _fake_dom_root_with_commission_tooltip():
    leaf = _FakeSimplifiedNode(
        original_node=_FakeOriginalNode("coin-hands-icon", parent_node=_FakeParentNode({"mattooltip": "Your share of the vendor's earnings"}))
    )
    return _FakeSimplifiedNode(children=[leaf])


def _knowledge() -> KnowledgeBase:
    return KnowledgeBase(store=_FakeStore())


def test_knowledge_none_by_default_grounding_never_attempted_backward_compat():
    """Purely additive: every existing caller/test that never passes
    knowledge= keeps run_discovery()'s exact original behavior -- no
    grounding attempted, advancer never asked for include_dom."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA")])], dom_roots=[_fake_dom_root_with_commission_tooltip()])
    catalog = _catalog()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert advancer.received_include_dom == [False]


def test_real_dom_root_grounds_a_real_tooltip_field_automatically():
    """The core Blocker 1 proof: run_discovery() ITSELF, given a real
    KnowledgeBase, grounds a real field from a real (fake-shaped) DOM
    tree -- no diagnostic script, no manual call from outside this
    function."""
    from atlas.brain.marketplace_semantic_grounding import field_grounding

    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    changed = _snapshot([("A", "vendorA"), ("B", "vendorB")])
    advancer = _FakeAdvancer(
        [changed, changed],  # 2nd identical to 1st -> stops via content_change_timeout
        dom_roots=[_fake_dom_root_with_commission_tooltip(), None],
    )
    catalog = _catalog()
    knowledge = _knowledge()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, knowledge=knowledge)

    claim = field_grounding("commission_pct", knowledge)
    assert claim is not None
    assert claim.object_value == "Your share of the vendor's earnings"
    assert claim.claim_type == "observation"
    assert advancer.received_include_dom == [True, True]


def test_grounding_is_idempotent_across_multiple_cycles():
    from atlas.brain.marketplace_semantic_grounding import field_grounding

    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    root = _fake_dom_root_with_commission_tooltip()
    third = _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")])
    advancer = _FakeAdvancer(
        [
            _snapshot([("A", "vendorA"), ("B", "vendorB")]),
            third,
            third,  # repeats -> stops via content_change_timeout, never IndexErrors on a 4th call
        ],
        dom_roots=[root, root, root],
    )
    catalog = _catalog()
    knowledge = _knowledge()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, knowledge=knowledge)

    assert field_grounding("commission_pct", knowledge) is not None
    assert len(knowledge.claims(subject_id="digistore24_marketplace:field:commission_pct", predicate="means")) == 1


def test_labeled_field_grounds_from_the_very_first_dom_less_cycle():
    """ground_labeled_fields() needs only text_content, not dom_root --
    must ground net_earnings_per_sale even on the baseline observe()
    cycle, before any real scroll/DOM access happens."""
    from atlas.brain.marketplace_semantic_grounding import field_grounding

    baseline_text = _product_block("A", "vendorA")  # already contains the real "Net earnings/sale" label
    observer = _FakeObserver(baseline_text)
    advancer = _FakeAdvancer([baseline_text])  # unchanged -> stops after cycle 1, no dom_root ever supplied
    catalog = _catalog()
    knowledge = _knowledge()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, knowledge=knowledge)

    claim = field_grounding("net_earnings_per_sale", knowledge)
    assert claim is not None
    assert claim.predicate == "labeled_as"
    assert claim.object_value == "Net earnings/sale"


# --- Orientation Precondition + Completeness Wiring (2026-08-16) -----------

from atlas.brain.marketplace_discovery import DiscoveryRunResult  # noqa: E402
from atlas.integrations.traversal_completion import PageCompletionTracker  # noqa: E402


def test_orientation_already_at_top_skips_reverse_traversal():
    """pages_above already near-zero -> zero orientation scrolls, the
    existing forward-only behavior is completely undisturbed."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=0.0))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=0.0, pages_above=0.0)])
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.orientation_scrolls_used == 0
    assert advancer.call_count == 1  # exactly one forward-traversal call, no orientation calls
    assert result.stop_reason == "pages_below_indicates_end"


class _DirectionTrackingAdvancer:
    """Like _FakeAdvancer, but also records the `direction` kwarg of every
    call, so orientation (direction='up') calls can be told apart from
    forward-traversal (direction='down'/default) calls explicitly.

    2026-08-17, live-validation-caught bug fix: when no `content_changed`
    callback is given, this MUST default to False, exactly mirroring the
    real DiscoveryScrollAdvancer._advance_async()'s own behavior
    ("changed = False" when content_changed is None) -- the original
    `else True` here was a LYING fake that let the real orientation bug
    (no callback ever passed) hide behind a false-positive test result.
    A test double must reflect production's real contract, never a more
    convenient one."""

    def __init__(self, texts: list[str], url: str = URL):
        self._texts = texts
        self._url = url
        self.call_count = 0
        self.directions: list[str] = []

    def advance(self, url, verify_target=None, content_changed=None, direction="down", include_dom=False, **kwargs):
        text = self._texts[self.call_count]
        self.directions.append(direction)
        self.call_count += 1
        if verify_target is not None and not verify_target(self._url):
            raise BrowserUseError("target mismatch during scroll")
        changed = content_changed(text) if content_changed is not None else False
        return ScrollAdvanceResult(text_content=text, url=self._url, content_changed=changed)


def test_orientation_starts_mid_page_climbs_to_top_before_forward_traversal():
    """pages_above starts > threshold, decreases across successive
    direction='up' calls until near-zero -- THEN forward traversal
    (direction='down') begins. Each orientation step reveals a genuinely
    DIFFERENT product set (not just a different pages_above number on an
    identical product) -- real content_changed is identity-based
    (dedupe_key-set comparison), the same as a real scroll actually
    revealing/hiding real cards."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=1.2))
    advancer = _DirectionTrackingAdvancer(
        [
            _snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=5.0, pages_above=0.6),  # orientation climb 1 -- new product revealed
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")], pages_below=5.0, pages_above=0.0),  # climb 2 -> oriented
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC"), ("D", "vendorD")], pages_below=0.0, pages_above=0.0),  # forward
        ]
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert advancer.directions == ["up", "up", "down"]
    assert result.orientation_scrolls_used == 2
    # The text reached at the end of orientation becomes forward-traversal
    # cycle 1 (pages_below=5.0 there, doesn't stop yet); the real "down"
    # scroll produces cycle 2, which does have pages_below=0.0.
    assert result.cycles_run == 2
    assert result.stop_reason == "pages_below_indicates_end"


def test_orientation_starts_at_bottom_climbs_to_top_before_forward_traversal():
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=0.0, pages_above=2.5))
    advancer = _DirectionTrackingAdvancer(
        [
            _snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=0.0, pages_above=1.0),
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")], pages_below=0.0, pages_above=0.0),
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC"), ("D", "vendorD")], pages_below=0.0, pages_above=0.0),
        ]
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert advancer.directions[:2] == ["up", "up"]
    assert result.orientation_scrolls_used == 2


def test_pages_below_near_zero_at_start_while_not_oriented_never_causes_false_completion():
    """The exact Page-3 bug: browser starts at the bottom
    (pages_below≈0) but NOT at the top (pages_above>0). Orientation must
    run BEFORE the pages_below stop-check is ever consulted."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=0.0, pages_above=1.0))
    advancer = _DirectionTrackingAdvancer(
        [
            _snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=0.0, pages_above=0.0),  # oriented
            _snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")], pages_below=0.0, pages_above=0.0),
        ]
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert advancer.directions[0] == "up"  # oriented first, not immediately declared complete
    assert result.orientation_scrolls_used == 1
    assert result.cycles_run == 1  # real forward traversal did happen after orientation


# --- Real-bug regression: content_changed must be identity-based, never a
# fake/hardcoded default (2026-08-17, live-validation-caught) -----------


def test_reverse_scroll_with_real_new_content_is_never_mistaken_for_no_progress():
    """Direct regression test for the live-validation bug: a reverse
    scroll that genuinely reveals a different product set (proven live:
    pages_above 2.3->0.7, a new product appeared, an old one scrolled out
    of view) must be recognized as real progress, not stopped as
    orientation_failed after one attempt. Before the fix, this exact
    shape would have failed immediately (result.content_changed was
    unconditionally False whenever no callback was passed) -- proven by
    _DirectionTrackingAdvancer now correctly defaulting to False and
    still passing here, because run_discovery() supplies a REAL,
    identity-based callback."""
    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=1.6, pages_above=2.3))
    advancer = _DirectionTrackingAdvancer(
        [
            # "B" scrolled out of view, "C" newly revealed -- a genuinely
            # different product set, mirroring the real live capture.
            _snapshot([("A", "vendorA"), ("C", "vendorC")], pages_below=1.6, pages_above=0.7),
            # "E" also newly revealed on this pass -- differs from the
            # previous step too, and reaches the top.
            _snapshot([("A", "vendorA"), ("C", "vendorC"), ("E", "vendorE")], pages_below=1.0, pages_above=0.0),
            _snapshot([("A", "vendorA"), ("C", "vendorC"), ("E", "vendorE"), ("D", "vendorD")], pages_below=0.0, pages_above=0.0),
        ]
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason != "orientation_failed"
    assert result.orientation_scrolls_used == 2
    assert advancer.directions == ["up", "up", "down"]  # oriented, then real forward traversal follows


def test_reverse_scroll_with_genuinely_identical_content_fails_closed():
    """The symmetric, correct-rejection case: when a reverse scroll
    produces the EXACT same product set (real "can't climb further"),
    orientation must still fail closed -- the fix must not make
    everything look like progress."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=3.0))
    advancer = _DirectionTrackingAdvancer(
        [_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=3.0)]  # identical product set -- no real change
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "orientation_failed"
    assert result.cycles_run == 0


def test_new_records_from_a_reverse_scroll_are_preserved_even_when_orientation_then_fails():
    """A reverse scroll reveals genuinely new products, but the very next
    check exhausts max_orientation_scrolls before reaching the top --
    the new products seen during that one successful scroll must still
    be preserved, even though the overall orientation run ends in
    orientation_failed."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=3.0))
    advancer = _DirectionTrackingAdvancer(
        [_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")], pages_below=5.0, pages_above=1.5)]
    )
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, max_orientation_scrolls=1)

    assert result.stop_reason == "orientation_failed"
    assert result.cycles_run == 0
    # A and B/C (new, revealed by the one real scroll that happened)
    # must both be preserved -- not just the baseline A.
    assert catalog.known_keys() == {"vendora::a", "vendorb::b", "vendorc::c"}
    assert result.total_new_records == 3


def test_new_records_from_a_reverse_scroll_reach_the_tracker_even_when_orientation_then_fails():
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=3.0))
    advancer = _DirectionTrackingAdvancer(
        [_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=5.0, pages_above=1.5)]
    )
    catalog = _catalog()
    tracker = PageCompletionTracker()

    result = run_discovery(
        URL, observer, advancer, catalog, verify_target=_always_true, tracker=tracker, max_orientation_scrolls=1
    )

    assert result.stop_reason == "orientation_failed"
    assert {r.key for r in tracker.records()} == {"vendora::a", "vendorb::b"}


def test_orientation_that_cannot_reach_top_stops_and_reports_orientation_failed():
    """Content never changes on reverse scroll -- can't climb further.
    Must stop with orientation_failed, never proceed to forward
    traversal, never fabricate reaching the top."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=3.0))

    class _StuckAdvancer:
        def __init__(self):
            self.call_count = 0
            self.directions = []

        def advance(self, url, verify_target=None, content_changed=None, direction="down", include_dom=False, **kwargs):
            self.directions.append(direction)
            self.call_count += 1
            # Always returns the identical text -- no real progress possible.
            return ScrollAdvanceResult(
                text_content=_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=3.0),
                url=URL,
                content_changed=False,
            )

    advancer = _StuckAdvancer()
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "orientation_failed"
    assert result.cycles_run == 0  # forward traversal was never reached
    assert all(d == "up" for d in advancer.directions)
    assert advancer.call_count == 1  # stopped immediately on the first no-progress reverse scroll


def test_orientation_bound_exhausted_stops_and_reports_orientation_failed():
    """Real, gradual progress each pass, but never actually reaches
    near-zero within max_orientation_scrolls -- must stop bounded, never
    loop forever."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=10.0))

    class _SlowClimbAdvancer:
        def __init__(self):
            self.call_count = 0
            self.directions = []

        def advance(self, url, verify_target=None, content_changed=None, direction="down", include_dom=False, **kwargs):
            self.directions.append(direction)
            self.call_count += 1
            remaining = max(0.0, 10.0 - 0.5 * self.call_count)  # decreases too slowly to ever reach the threshold in 3 passes
            return ScrollAdvanceResult(
                text_content=_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=remaining),
                url=URL,
                content_changed=True,
            )

    advancer = _SlowClimbAdvancer()
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, max_orientation_scrolls=3)

    assert result.stop_reason == "orientation_failed"
    assert result.cycles_run == 0
    assert result.orientation_scrolls_used == 3
    assert advancer.call_count == 3  # bounded, never a 4th attempt


def test_orientation_failed_still_persists_real_records_observed_along_the_way():
    """No fabrication in either direction: a failed orientation still
    keeps whatever real records were genuinely seen during the climb."""
    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=5.0, pages_above=3.0))

    class _StuckAdvancer:
        def advance(self, url, verify_target=None, content_changed=None, direction="down", include_dom=False, **kwargs):
            return ScrollAdvanceResult(
                text_content=_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=5.0, pages_above=3.0),
                url=URL,
                content_changed=False,
            )

    advancer = _StuckAdvancer()
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "orientation_failed"
    assert result.total_new_records == 2  # A and B were real, seen, and persisted
    assert catalog.known_keys() == {"vendora::a", "vendorb::b"}


def test_tracker_observes_every_record_extracted_across_the_whole_run():
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=0.0))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=0.0, pages_above=0.0)])
    catalog = _catalog()
    tracker = PageCompletionTracker()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, tracker=tracker)

    assert {r.key for r in tracker.records()} == {"vendora::a", "vendorb::b"}


def test_tracker_none_by_default_backward_compatible():
    """No tracker passed -> run_discovery() behaves exactly as before
    this wiring existed; no crash, no implicit tracker created."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=0.0))
    advancer = _FakeAdvancer([])
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "pages_below_indicates_end"


def test_unknown_stays_unknown_inspection_never_marked_resolved_without_a_real_mechanism():
    """Design Lock: no inspect_fn/resolve() mechanism is wired this
    round -- every observed record must honestly stay
    'not_yet_inspected', and is_page_complete() must never report True,
    even when content is fully complete."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=0.0))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=0.0, pages_above=0.0)])
    catalog = _catalog()
    tracker = PageCompletionTracker()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, tracker=tracker)

    assert result.stop_reason == "pages_below_indicates_end"  # real content-completeness signal
    assert tracker.is_inspection_complete() is False  # nothing was ever inspected/resolved
    content_complete = result.stop_reason == "pages_below_indicates_end"
    assert tracker.is_page_complete(content_complete) is False  # honestly incomplete, not fabricated


def test_orientation_and_tracker_do_not_break_existing_semantic_grounding():
    """Combining the new orientation phase with existing Semantic
    Grounding wiring: grounding still happens correctly on the first real
    forward-traversal cycle after a mid-page start."""
    from atlas.brain.marketplace_semantic_grounding import field_grounding

    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=1.0))
    changed = _snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=5.0, pages_above=0.0)
    stable = _snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=5.0, pages_above=0.0)

    class _MixedAdvancer:
        def __init__(self):
            self._calls = [
                ScrollAdvanceResult(
                    text_content=_snapshot([("A", "vendorA")], pages_below=5.0, pages_above=0.0),
                    url=URL,
                    content_changed=True,
                ),  # orientation climb -> oriented
                ScrollAdvanceResult(text_content=changed, url=URL, content_changed=True, dom_root=_fake_dom_root_with_commission_tooltip()),
                ScrollAdvanceResult(text_content=stable, url=URL, content_changed=False),
            ]
            self.i = 0

        def advance(self, url, verify_target=None, content_changed=None, direction="down", include_dom=False, **kwargs):
            result = self._calls[self.i]
            self.i += 1
            return result

    advancer = _MixedAdvancer()
    catalog = _catalog()
    knowledge = _knowledge()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, knowledge=knowledge)

    assert field_grounding("commission_pct", knowledge) is not None


# --- Canonical Identity through run_discovery() (2026-08-17, Cognitive
# State Wiring -- Audit finding: Catalog=10, Tracker=11 on the same real
# Page 3) ---------------------------------------------------------------


def test_tracker_and_catalog_end_with_the_same_identity_count_despite_vendor_missing_pass():
    """The exact live-audit finding, reproduced deterministically:
    vendor missing in one cycle's card, present in another, for the SAME
    real product -- Tracker must end with the same identity count as
    Catalog, never a phantom 11th entry."""

    baseline = _snapshot([("Unlock Earnings! Promote PinealXT!", "Nutraville")], pages_below=1.0)
    # A later cycle observes the same real card mid-partial-render, vendor empty.
    vendor_missing_cycle = _snapshot([("Unlock Earnings! Promote PinealXT!", "")], pages_below=0.0)

    observer = _FakeObserver(baseline)
    advancer = _FakeAdvancer([vendor_missing_cycle])
    catalog = _catalog()
    tracker = PageCompletionTracker()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, tracker=tracker)

    assert len(catalog.known_keys()) == 1
    assert len({r.key for r in tracker.records()}) == 1
    assert catalog.known_keys() == {r.key for r in tracker.records()}  # same canonical identity, not a divergence


def test_no_dom_root_this_cycle_leaves_field_unknown_never_fabricated():
    """Fail-closed, unconditional: if a cycle's dom_root is unavailable
    (None), nothing is grounded -- the field stays honestly UNKNOWN, no
    hardcoded/guessed meaning fills the gap."""
    from atlas.brain.marketplace_semantic_grounding import field_grounding

    observer = _FakeObserver(_snapshot([("A", "vendorA")]))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA")])], dom_roots=[None])
    catalog = _catalog()
    knowledge = _knowledge()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, knowledge=knowledge)

    assert field_grounding("commission_pct", knowledge) is None


# --- Forward Traversal Stop Condition fix (2026-08-17, Live Validation v2
# external-screenshot finding: a run stopped on no_new_products alone while
# real content ("Start Affiliate Marketing like a Pro") remained below the
# fold). Discovery stagnation (no_new_products) and traversal exhaustion
# (pages_below_indicates_end) are separate claims -- no_new_products may
# only actually stop the run when there is no real evidence more content
# exists below. ------------------------------------------------------------


def test_no_new_products_does_not_stop_while_real_pages_below_evidence_remains():
    """The exact Live Validation v2 finding, reproduced: every cycle finds
    zero NEW keys (catalog pre-seeded with everything that will be seen),
    but pages_below stays real and positive for three cycles -- traversal
    must continue regardless, only stopping once pages_below itself
    genuinely reaches near-zero."""
    catalog = _catalog()
    catalog.save_records(_records_from_snapshot(_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")])))

    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=3.0))
    advancer = _FakeAdvancer(
        [
            _snapshot([("B", "vendorB"), ("C", "vendorC")], pages_below=2.0),  # no new keys, real evidence more below
            _snapshot([("C", "vendorC"), ("A", "vendorA")], pages_below=1.0),  # still no new keys, still more below
            _snapshot([("A", "vendorA")], pages_below=0.0),  # finally at the real bottom
        ]
    )

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "pages_below_indicates_end"
    assert result.cycles_run == 4  # never stopped early on no_new_products


def test_no_new_products_still_stops_when_there_is_no_pages_below_signal_at_all():
    """The symmetric, correct case: when there is genuinely no scroll-
    region signal (pages_below is None, not merely absent-of-new-content),
    no_new_products must still be allowed to stop -- absence of evidence
    is not evidence of more content, and must not block a real
    stagnation-based stop forever."""
    catalog = _catalog()
    catalog.save_records(_records_from_snapshot(_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC"), ("D", "vendorD")])))

    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")]))  # no pages_below at all -> None
    advancer = _FakeAdvancer(
        [
            _snapshot([("C", "vendorC"), ("D", "vendorD")]),  # genuinely different set, but both already known, still no signal
        ]
    )

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "no_new_products"


def test_content_change_timeout_is_never_silently_treated_as_page_complete():
    """Same key-set on a real scroll (content_change_timeout) is a
    genuinely different, honest stop reason from pages_below_indicates_end
    -- a caller computing content_complete the documented way must see
    False here, never accidentally True."""
    observer = _FakeObserver(_snapshot([("A", "vendorA")], pages_below=2.0))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA")], pages_below=2.0)])  # identical -> no content change
    catalog = _catalog()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "content_change_timeout"
    content_complete = result.stop_reason == "pages_below_indicates_end"
    assert content_complete is False


def test_start_at_top_traverses_through_a_stagnant_stretch_to_the_real_bottom():
    """End-to-end: orientation not needed (already at top), forward
    traversal survives a real stagnant-but-more-below stretch, and still
    reaches a genuine, evidence-based bottom."""
    catalog = _catalog()
    catalog.save_records(_records_from_snapshot(_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")])))

    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=4.0, pages_above=0.0))
    advancer = _FakeAdvancer(
        [
            _snapshot([("B", "vendorB"), ("C", "vendorC")], pages_below=2.0, pages_above=0.0),  # different set, still all known
            _snapshot([("C", "vendorC")], pages_below=0.0, pages_above=0.0),  # different set again, real bottom
        ]
    )

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true)

    assert result.stop_reason == "pages_below_indicates_end"
    assert result.orientation_scrolls_used == 0  # already oriented, no reverse scroll needed


def test_records_seen_during_a_stagnant_stretch_still_reach_the_tracker():
    """Even when no new IDENTITY appears, the act of continuing to scroll
    still means whatever is currently visible gets observed -- data is
    never silently skipped just because nothing new was found."""
    catalog = _catalog()
    catalog.save_records(_records_from_snapshot(_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")])))

    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=2.0))
    advancer = _FakeAdvancer(
        [
            _snapshot([("B", "vendorB"), ("C", "vendorC")], pages_below=0.0),
        ]
    )
    tracker = PageCompletionTracker()

    run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, tracker=tracker)

    assert {r.key for r in tracker.records()} == {"vendora::a", "vendorb::b", "vendorc::c"}


def test_page_not_declared_complete_due_to_no_new_products_alone_even_with_tracker():
    """Design Lock, reaffirmed: inspection_complete/page_complete must
    never flip to True just because traversal kept going past a
    no_new_products-shaped stretch -- no resolve() mechanism exists yet,
    so every observed record honestly stays not_yet_inspected regardless
    of how the run stopped."""
    catalog = _catalog()

    observer = _FakeObserver(_snapshot([("A", "vendorA"), ("B", "vendorB")], pages_below=2.0))
    advancer = _FakeAdvancer([_snapshot([("A", "vendorA"), ("B", "vendorB"), ("C", "vendorC")], pages_below=0.0)])
    tracker = PageCompletionTracker()

    result = run_discovery(URL, observer, advancer, catalog, verify_target=_always_true, tracker=tracker)

    content_complete = result.stop_reason == "pages_below_indicates_end"
    assert content_complete is True  # real, honest content signal
    assert tracker.is_inspection_complete() is False  # still honestly incomplete
    assert tracker.is_page_complete(content_complete) is False  # never fabricated
