import pytest

from atlas.hands.models import HandsRequest
from atlas.hands.registry import HandsRequestRegistry


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_save_and_read_back_a_real_request_round_trips():
    registry = HandsRequestRegistry(store=_FakeStore())
    request = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}], reversible=True)

    registry.save_request(request)
    fetched = registry.get_request(request.id)

    assert fetched.id == request.id
    assert fetched.goal_id == "g1"
    assert fetched.reversible is True
    assert fetched.steps == [{"kind": "navigate", "params": {"url": "u"}}]


def test_get_request_raises_for_an_unknown_id():
    registry = HandsRequestRegistry(store=_FakeStore())
    with pytest.raises(KeyError):
        registry.get_request("does-not-exist")


def test_requests_for_goal_filters_correctly():
    registry = HandsRequestRegistry(store=_FakeStore())
    r1 = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}])
    r2 = HandsRequest(goal_id="g2", steps=[{"kind": "navigate", "params": {"url": "u"}}])
    registry.save_request(r1)
    registry.save_request(r2)

    result = registry.requests_for_goal("g1")

    assert len(result) == 1
    assert result[0].id == r1.id
