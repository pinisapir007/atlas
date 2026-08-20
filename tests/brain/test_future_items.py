import pytest

from atlas.brain.future_items import TRIGGER_CHECKS, UNWIRED_TRIGGER_CHECK, due_future_items, is_valid_trigger_check, resolve_future_item
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import FutureItem


def _kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path / "knowledge.json")


def _candidate(**overrides) -> FutureItem:
    defaults = dict(
        type="candidate",
        title="A real deferred idea",
        rationale="Identified during external research",
        trigger_description="Some real, checkable future condition",
        trigger_check=UNWIRED_TRIGGER_CHECK,
    )
    defaults.update(overrides)
    return FutureItem(**defaults)


@pytest.fixture(autouse=True)
def _clean_trigger_registry():
    """TRIGGER_CHECKS is a real, module-level, growable registry -- tests
    that register a fake predicate must not leak it into other tests."""
    original = dict(TRIGGER_CHECKS)
    yield
    TRIGGER_CHECKS.clear()
    TRIGGER_CHECKS.update(original)


# --- is_valid_trigger_check ----------------------------------------------


def test_unwired_trigger_check_is_always_valid():
    assert is_valid_trigger_check(UNWIRED_TRIGGER_CHECK) is True


def test_unregistered_trigger_check_is_invalid():
    assert is_valid_trigger_check("something_made_up") is False


def test_a_registered_trigger_check_is_valid():
    TRIGGER_CHECKS["real_predicate"] = lambda: True
    assert is_valid_trigger_check("real_predicate") is True


# --- due_future_items -----------------------------------------------------


def test_unwired_items_never_appear_as_trigger_fired(tmp_path):
    kb = _kb(tmp_path)
    kb.save_future_item(_candidate(trigger_check=UNWIRED_TRIGGER_CHECK))

    due = due_future_items(kb)

    assert due["trigger_fired"] == []
    assert len(due["unwired"]) == 1


def test_a_real_registered_trigger_that_evaluates_true_is_reported_as_fired(tmp_path):
    TRIGGER_CHECKS["always_true"] = lambda: True
    kb = _kb(tmp_path)
    kb.save_future_item(_candidate(trigger_check="always_true"))

    due = due_future_items(kb)

    assert len(due["trigger_fired"]) == 1
    assert due["unwired"] == []


def test_a_real_registered_trigger_that_evaluates_false_is_not_reported(tmp_path):
    TRIGGER_CHECKS["always_false"] = lambda: False
    kb = _kb(tmp_path)
    kb.save_future_item(_candidate(trigger_check="always_false"))

    due = due_future_items(kb)

    assert due["trigger_fired"] == []
    assert due["unwired"] == []


def test_resolved_items_never_appear_in_either_bucket_even_if_trigger_is_true(tmp_path):
    TRIGGER_CHECKS["always_true"] = lambda: True
    kb = _kb(tmp_path)
    item = _candidate(trigger_check="always_true")
    kb.save_future_item(item)
    resolve_future_item(item.id, "reject", "not worth pursuing", kb)

    due = due_future_items(kb)

    assert due["trigger_fired"] == []
    assert due["unwired"] == []


def test_due_future_items_recomputes_fresh_every_call_never_a_one_shot_notification(tmp_path):
    """The structural guarantee against forgetting: calling due_future_
    items() twice in a row for the same unresolved, fired item returns it
    both times -- there is no 'already notified' state anywhere to make
    the second call silent."""
    TRIGGER_CHECKS["always_true"] = lambda: True
    kb = _kb(tmp_path)
    kb.save_future_item(_candidate(trigger_check="always_true"))

    first_call = due_future_items(kb)
    second_call = due_future_items(kb)

    assert len(first_call["trigger_fired"]) == 1
    assert len(second_call["trigger_fired"]) == 1
    assert first_call["trigger_fired"][0].id == second_call["trigger_fired"][0].id


# --- resolve_future_item ---------------------------------------------------


def test_resolve_future_item_rejects_unknown_resolution(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    with pytest.raises(ValueError, match="unknown FutureItem resolution"):
        resolve_future_item(item.id, "maybe", "unclear", kb)


def test_resolve_future_item_implement_marks_resolved(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    resolved, new_item = resolve_future_item(item.id, "implement", "worth building now", kb)

    assert resolved.status == "resolved"
    assert resolved.resolution == "implement"
    assert resolved.resolved_at is not None
    assert new_item is None
    assert kb.get_future_item(item.id).status == "resolved"


def test_resolve_future_item_reject_marks_resolved_no_new_item(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    resolved, new_item = resolve_future_item(item.id, "reject", "not aligned with trust principles", kb)

    assert resolved.resolution == "reject"
    assert new_item is None


def test_resolve_future_item_already_satisfied_marks_resolved_no_new_item(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    resolved, new_item = resolve_future_item(item.id, "already_satisfied", "covered by an existing mechanism", kb)

    assert resolved.resolution == "already_satisfied"
    assert new_item is None


def test_resolve_future_item_deferred_again_requires_a_next_trigger_check(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    with pytest.raises(ValueError, match="requires a real next_trigger_check"):
        resolve_future_item(item.id, "deferred_again", "still too early", kb)


def test_resolve_future_item_deferred_again_rejects_unknown_next_trigger_check(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    with pytest.raises(ValueError, match="unknown trigger_check"):
        resolve_future_item(item.id, "deferred_again", "still too early", kb, next_trigger_check="made_up")


def test_resolve_future_item_deferred_again_creates_a_new_chained_item(tmp_path):
    TRIGGER_CHECKS["real_future_check"] = lambda: False
    kb = _kb(tmp_path)
    item = _candidate(title="Real deferred idea")
    kb.save_future_item(item)

    resolved, new_item = resolve_future_item(item.id, "deferred_again", "still too early", kb, next_trigger_check="real_future_check")

    assert resolved.status == "resolved"
    assert resolved.resolution == "deferred_again"
    assert resolved.superseded_by_id == new_item.id
    assert new_item.title == "Real deferred idea"
    assert new_item.trigger_check == "real_future_check"
    assert new_item.status == "open"
    assert kb.get_future_item(new_item.id).id == new_item.id  # really persisted, not just returned


def test_resolve_future_item_deferred_again_can_defer_to_unwired_again(tmp_path):
    kb = _kb(tmp_path)
    item = _candidate()
    kb.save_future_item(item)

    resolved, new_item = resolve_future_item(item.id, "deferred_again", "still no real predicate", kb, next_trigger_check=UNWIRED_TRIGGER_CHECK)

    assert new_item.trigger_check == UNWIRED_TRIGGER_CHECK


def test_resolve_future_item_raises_on_missing_item(tmp_path):
    kb = _kb(tmp_path)
    with pytest.raises(KeyError):
        resolve_future_item("does-not-exist", "reject", "n/a", kb)
