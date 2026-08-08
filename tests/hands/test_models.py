import pytest

from atlas.hands.models import HandsRequest, InvalidHandsRequestError, validate_steps


def test_validate_steps_rejects_an_empty_list():
    with pytest.raises(InvalidHandsRequestError, match="at least one step"):
        validate_steps([])


def test_validate_steps_rejects_an_unrecognized_kind():
    with pytest.raises(InvalidHandsRequestError, match="unrecognized"):
        validate_steps([{"kind": "not_a_real_kind", "params": {}}])


def test_validate_steps_rejects_mixed_browser_and_desktop_kinds():
    with pytest.raises(InvalidHandsRequestError, match="mix browser and desktop"):
        validate_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}, {"kind": "type_text", "params": {"text": "hi"}}])


def test_validate_steps_accepts_a_real_homogeneous_browser_sequence():
    validate_steps([{"kind": "navigate", "params": {"url": "https://example.com"}}, {"kind": "click", "params": {"index": 1}}])


def test_validate_steps_accepts_a_real_homogeneous_desktop_sequence():
    validate_steps([{"kind": "launch_app", "params": {"path": "notepad.exe"}}, {"kind": "type_text", "params": {"text": "hi"}}])


def test_executor_reports_browser_for_browser_steps():
    request = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}])
    assert request.executor() == "browser"


def test_executor_reports_desktop_for_desktop_steps():
    request = HandsRequest(goal_id="g1", steps=[{"kind": "type_text", "params": {"text": "hi"}}])
    assert request.executor() == "desktop"


def test_default_reversible_is_false_fail_closed():
    request = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}])
    assert request.reversible is False
