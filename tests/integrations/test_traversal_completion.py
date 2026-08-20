from dataclasses import dataclass

import pytest

from atlas.integrations.browser_use_observer import BrowserUseError
from atlas.integrations.traversal_completion import (
    MAX_REVISIT_PASSES,
    PageCompletionTracker,
    revisit_until_resolved,
)

_URL = "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all"


# --- Serialization (2026-08-17, Cognitive State Wiring) -------------------


def test_to_dict_from_dict_round_trips_pending_state():
    tracker = PageCompletionTracker()
    tracker.observe("a", {"price": 10})

    restored = PageCompletionTracker.from_dict(tracker.to_dict())

    assert restored.pending_keys() == ["a"]
    assert [r.data for r in restored.records()] == [{"price": 10}]


def test_to_dict_from_dict_round_trips_resolved_state():
    tracker = PageCompletionTracker()
    tracker.observe("a", {})
    tracker.resolve("a", "inspected")

    restored = PageCompletionTracker.from_dict(tracker.to_dict())

    assert restored.pending_keys() == []
    assert restored.is_inspection_complete() is True


def test_from_dict_of_empty_data_is_a_valid_empty_tracker():
    restored = PageCompletionTracker.from_dict({})
    assert restored.records() == []
    assert restored.is_inspection_complete() is True


# --- PageCompletionTracker: pure bookkeeping, no browser interaction -------


def test_observe_adds_a_new_key_as_not_yet_inspected():
    tracker = PageCompletionTracker()
    is_new = tracker.observe("product-a", {"name": "Product A"})

    assert is_new is True
    assert tracker.pending_keys() == ["product-a"]


def test_observe_refreshing_a_known_key_never_resets_its_inspection_state():
    """Virtualization safety: a card that scrolled out of view and back
    into view must not lose progress already made on it."""
    tracker = PageCompletionTracker()
    tracker.observe("product-a", {"name": "v1"})
    tracker.resolve("product-a", "inspected")

    is_new = tracker.observe("product-a", {"name": "v1-refreshed"})

    assert is_new is False
    assert tracker.pending_keys() == []  # still resolved, not reset
    assert [r for r in tracker.records() if r.key == "product-a"][0].data == {"name": "v1-refreshed"}


def test_resolve_rejects_an_unknown_key():
    tracker = PageCompletionTracker()
    with pytest.raises(KeyError):
        tracker.resolve("never-observed", "inspected")


def test_resolve_rejects_not_yet_inspected_as_a_target_state():
    tracker = PageCompletionTracker()
    tracker.observe("product-a", {})
    with pytest.raises(ValueError):
        tracker.resolve("product-a", "not_yet_inspected")


def test_resolve_rejects_an_invalid_state():
    tracker = PageCompletionTracker()
    tracker.observe("product-a", {})
    with pytest.raises(ValueError):
        tracker.resolve("product-a", "definitely_fine_trust_me")


def test_observe_never_creates_duplicate_records_for_the_same_key():
    tracker = PageCompletionTracker()
    tracker.observe("product-a", {"v": 1})
    tracker.observe("product-a", {"v": 2})
    tracker.observe("product-a", {"v": 3})

    assert len(tracker.records()) == 1


def test_page_not_complete_with_ten_products_and_four_not_inspected():
    tracker = PageCompletionTracker()
    for i in range(10):
        tracker.observe(f"product-{i}", {})
    for i in range(6):
        tracker.resolve(f"product-{i}", "inspected")
    # products 6,7,8,9 remain not_yet_inspected

    assert tracker.is_page_complete(content_complete=True) is False
    assert set(tracker.unresolved_report()) == {"product-6", "product-7", "product-8", "product-9"}


def test_page_complete_only_when_content_and_inspection_both_complete():
    tracker = PageCompletionTracker()
    tracker.observe("product-a", {})
    tracker.resolve("product-a", "inspected")

    assert tracker.is_page_complete(content_complete=False) is False  # inspection done, content not
    assert tracker.is_page_complete(content_complete=True) is True


def test_proven_missing_counts_as_resolved_not_as_a_gap():
    """Design Lock precedent (Prime Perform Supplement EN): a record that
    is genuinely confirmed to have no detail link is COMPLETE, not an
    outstanding gap."""
    tracker = PageCompletionTracker()
    tracker.observe("product-a", {})
    tracker.observe("product-b", {})
    tracker.resolve("product-a", "inspected")
    tracker.resolve("product-b", "proven_missing")

    assert tracker.is_inspection_complete() is True
    assert tracker.is_page_complete(content_complete=True) is True


# --- revisit_until_resolved(): orchestration ---------------------------------


@dataclass
class _FakeAdvanceResult:
    text_content: str
    url: str
    content_changed: bool
    selector_map: object = None


class _FakeAdvancer:
    """Duck-typed stand-in for DiscoveryScrollAdvancer -- returns one
    canned ScrollAdvanceResult-shaped object per successive call,
    repeating the last one if called more times than results supplied."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def advance(self, url, verify_target=None, direction="down", content_change_timeout=15.0, include_dom=False, **_kw):
        self.calls.append({"url": url, "direction": direction, "include_dom": include_dom})
        idx = min(len(self.calls) - 1, len(self._results) - 1)
        result = self._results[idx]
        # Mirrors the real DiscoveryScrollAdvancer: verify_target is
        # checked against the real, freshly-resolved post-action URL,
        # not the requested one -- a redirect during the real scroll is
        # exactly what this guards against.
        if verify_target is not None and not verify_target(result.url):
            raise BrowserUseError(f"target mismatch: {result.url!r}")
        return result


def _tracker_with_pending(keys):
    tracker = PageCompletionTracker()
    for k in keys:
        tracker.observe(k, {})
    return tracker


def test_revisit_resolves_three_and_marks_one_proven_missing_then_completes():
    """10 products, 4 not-inspected -> revisit resolves 3 + proves 1
    missing -> page becomes complete."""
    tracker = _tracker_with_pending([f"product-{i}" for i in range(10)])
    for i in range(6):
        tracker.resolve(f"product-{i}", "inspected")
    # product-6..9 pending

    def extract_fn(text):
        return [(f"product-{i}", {}) for i in range(10)]  # everything back in view during revisit

    resolutions = {"product-6": "inspected", "product-7": "inspected", "product-8": "inspected", "product-9": "proven_missing"}

    def inspect_fn(key, text, selector_map):
        return resolutions.get(key)

    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up-1", url=_URL, content_changed=True)])

    outcome = revisit_until_resolved(_URL, tracker, advancer, extract_fn, inspect_fn)

    assert outcome.stopped_reason == "all_resolved"
    assert outcome.resolved_this_run == 4
    assert outcome.remaining_pending == []
    assert tracker.is_page_complete(content_complete=True) is True


def test_revisit_stops_at_max_passes_and_reports_unresolved_explicitly():
    """A key that never resolves must never be silently forgotten --
    stops bounded, names exactly what's still unresolved."""
    tracker = _tracker_with_pending(["stubborn-product"])

    def extract_fn(text):
        return []

    def inspect_fn(key, text, selector_map):
        return None  # never resolves, no matter how many passes

    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up", url=_URL, content_changed=True)])

    outcome = revisit_until_resolved(_URL, tracker, advancer, extract_fn, inspect_fn, max_passes=3)

    assert outcome.stopped_reason in ("max_passes", "no_progress")
    assert outcome.passes_used <= 3
    assert outcome.remaining_pending == ["stubborn-product"]  # never fabricated success


def test_revisit_stops_on_no_progress_even_before_max_passes():
    tracker = _tracker_with_pending(["a", "b"])

    def extract_fn(text):
        return []

    def inspect_fn(key, text, selector_map):
        return None

    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up", url=_URL, content_changed=True)])

    outcome = revisit_until_resolved(_URL, tracker, advancer, extract_fn, inspect_fn, max_passes=MAX_REVISIT_PASSES)

    assert outcome.stopped_reason == "no_progress"
    assert outcome.passes_used == 1  # stopped after the very first pass resolved nothing


def test_revisit_never_leaves_the_verified_target_domain():
    tracker = _tracker_with_pending(["a"])
    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up", url="https://not-approved.example", content_changed=True)])

    with pytest.raises(BrowserUseError, match="target mismatch"):
        revisit_until_resolved(
            _URL, tracker, advancer, lambda t: [], lambda k, t, s: None, verify_target=lambda u: u == _URL
        )


def test_revisit_always_scrolls_up_with_dom_included():
    tracker = _tracker_with_pending(["a"])
    tracker.resolve("a", "inspected")  # nothing pending -> should never even call advance
    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up", url=_URL, content_changed=True)])

    revisit_until_resolved(_URL, tracker, advancer, lambda t: [], lambda k, t, s: None)

    assert advancer.calls == []  # already fully resolved -- no wasted real action


def test_revisit_direction_and_dom_flag_on_every_real_call():
    tracker = _tracker_with_pending(["a", "b"])

    def inspect_fn(key, text, selector_map):
        return "inspected" if key == "a" else None

    advancer = _FakeAdvancer(
        [
            _FakeAdvanceResult(text_content="pass-1", url=_URL, content_changed=True),
            _FakeAdvanceResult(text_content="pass-2", url=_URL, content_changed=True),
        ]
    )
    revisit_until_resolved(_URL, tracker, advancer, lambda t: [], lambda key, t, s: "inspected" if key == "a" else "proven_missing", max_passes=3)

    assert all(call["direction"] == "up" for call in advancer.calls)
    assert all(call["include_dom"] is True for call in advancer.calls)


def test_revisit_preserves_union_when_extract_fn_omits_a_previously_seen_key():
    """Virtualization removing an old card from a later extraction pass
    must never lose it from the tracker's union."""
    tracker = _tracker_with_pending(["a", "b"])

    def extract_fn(text):
        return [("a", {})]  # "b" has scrolled out of view this pass, must NOT disappear

    def inspect_fn(key, text, selector_map):
        return "inspected"

    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up", url=_URL, content_changed=True)])
    revisit_until_resolved(_URL, tracker, advancer, extract_fn, inspect_fn, max_passes=1)

    assert {r.key for r in tracker.records()} == {"a", "b"}


def test_revisit_reidentifies_by_key_regardless_of_pass_ordering():
    """Re-identification is by key, never by position/order across
    passes."""
    tracker = _tracker_with_pending(["x", "y", "z"])

    def inspect_fn(key, text, selector_map):
        # resolves keys in a different order than they were originally observed
        return {"z": "inspected", "x": "inspected", "y": "proven_missing"}.get(key)

    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="up", url=_URL, content_changed=True)])
    outcome = revisit_until_resolved(_URL, tracker, advancer, lambda t: [], inspect_fn, max_passes=1)

    assert outcome.resolved_this_run == 3
    assert outcome.remaining_pending == []


def test_inspect_fn_receives_the_synced_text_and_selector_map_from_the_same_advance_call():
    """The '48317 lesson', structurally enforced: inspect_fn must never
    see a text/selector_map pair assembled from two different reads."""
    tracker = _tracker_with_pending(["a"])
    seen = []
    fake_map = {1: "node"}

    def inspect_fn(key, text, selector_map):
        seen.append((text, selector_map))
        return "inspected"

    advancer = _FakeAdvancer([_FakeAdvanceResult(text_content="synced-text", url=_URL, content_changed=True, selector_map=fake_map)])
    revisit_until_resolved(_URL, tracker, advancer, lambda t: [], inspect_fn, max_passes=1)

    assert seen == [("synced-text", fake_map)]
