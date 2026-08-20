from atlas.brain.inspection_memory import InspectionMemoryStore
from atlas.integrations.traversal_completion import PageCompletionTracker


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _memory() -> InspectionMemoryStore:
    return InspectionMemoryStore(store=_FakeStore())


def test_load_tracker_for_an_unknown_page_key_returns_a_real_empty_tracker():
    memory = _memory()
    tracker = memory.load_tracker("https://example.com/page1")
    assert tracker.records() == []
    assert tracker.is_inspection_complete() is True


def test_save_then_load_round_trips_pending_state():
    memory = _memory()
    tracker = PageCompletionTracker()
    tracker.observe("a", {"price": 10})
    memory.save_tracker("page1", tracker)

    reloaded = memory.load_tracker("page1")

    assert reloaded.pending_keys() == ["a"]
    assert [r.data for r in reloaded.records()] == [{"price": 10}]


def test_save_then_load_round_trips_resolved_state():
    memory = _memory()
    tracker = PageCompletionTracker()
    tracker.observe("a", {})
    tracker.resolve("a", "inspected")
    memory.save_tracker("page1", tracker)

    reloaded = memory.load_tracker("page1")

    assert reloaded.is_inspection_complete() is True


def test_state_survives_a_brand_new_tracker_instance_i_e_process_recreation():
    """The exact real gap the Live Validation runs hit: a NEW
    PageCompletionTracker() object (standing in for a new process) must
    still see the previously-saved state once loaded from memory."""
    memory = _memory()
    original = PageCompletionTracker()
    original.observe("a", {})
    original.observe("b", {})
    original.resolve("a", "inspected")
    memory.save_tracker("page1", original)

    del original  # simulate the process/object genuinely being gone
    fresh = memory.load_tracker("page1")

    assert fresh.pending_keys() == ["b"]  # "a" stayed resolved, not reset
    assert {r.key for r in fresh.records()} == {"a", "b"}


def test_observation_never_resets_persisted_inspection_state():
    """Observation != Inspection: re-observing a product across a saved/
    reloaded tracker must never reset its resolved state."""
    memory = _memory()
    tracker = PageCompletionTracker()
    tracker.observe("a", {"price": 10})
    tracker.resolve("a", "inspected")
    memory.save_tracker("page1", tracker)

    reloaded = memory.load_tracker("page1")
    reloaded.observe("a", {"price": 12})  # re-observed with refreshed data
    memory.save_tracker("page1", reloaded)

    final = memory.load_tracker("page1")
    assert final.is_inspection_complete() is True  # still resolved
    assert [r.data for r in final.records()][0] == {"price": 12}  # data did refresh


def test_different_page_keys_are_independent():
    memory = _memory()
    tracker1 = PageCompletionTracker()
    tracker1.observe("a", {})
    memory.save_tracker("page1", tracker1)

    tracker2 = PageCompletionTracker()
    tracker2.observe("b", {})
    memory.save_tracker("page2", tracker2)

    assert {r.key for r in memory.load_tracker("page1").records()} == {"a"}
    assert {r.key for r in memory.load_tracker("page2").records()} == {"b"}
    assert set(memory.known_page_keys()) == {"page1", "page2"}


def test_backward_compatible_default_path_matches_atlas_dir_convention():
    """Same convention as every other real store in this codebase --
    .atlas/<name>.json -- confirmed via the constructor default, not a
    hardcoded guess."""
    import inspect

    sig = inspect.signature(InspectionMemoryStore.__init__)
    default_path = sig.parameters["path"].default
    assert str(default_path) in (".atlas/inspection_memory.json", ".atlas\\inspection_memory.json")
