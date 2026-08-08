from atlas.brain.memory import BrainMemory
from atlas.brain.risk import RiskPolicy
from atlas.hands.dispatch import HANDS_TASK_CATEGORY, request_hands_action
from atlas.hands.registry import HandsRequestRegistry


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _memory():
    return BrainMemory(store=_FakeStore())


def _hands_requests():
    return HandsRequestRegistry(store=_FakeStore())


def test_request_hands_action_saves_a_real_request_and_a_real_correlated_task():
    memory = _memory()
    hands_requests = _hands_requests()

    request = request_hands_action(
        memory,
        hands_requests,
        goal_id="goal-1",
        steps=[{"kind": "navigate", "params": {"url": "https://example.com"}}],
        reversible=True,
        description="real navigation test",
    )

    assert request.task_id is not None
    saved_request = hands_requests.get_request(request.id)
    assert saved_request.task_id == request.task_id

    tasks = memory.tasks()
    assert len(tasks) == 1
    assert tasks[0].id == request.task_id
    assert tasks[0].category == HANDS_TASK_CATEGORY
    assert tasks[0].source_opportunity_id == request.id
    assert tasks[0].reversible is True


def test_a_reversible_safe_request_does_not_require_founder_approval():
    memory = _memory()
    hands_requests = _hands_requests()
    request = request_hands_action(
        memory, hands_requests, goal_id="goal-1",
        steps=[{"kind": "navigate", "params": {"url": "https://example.com"}}],
        reversible=True,
    )
    task = memory.tasks()[0]

    decision = RiskPolicy().evaluate(task)

    assert decision.requires_approval is False


def test_an_irreversible_request_requires_founder_approval_fail_closed():
    memory = _memory()
    hands_requests = _hands_requests()
    request_hands_action(
        memory, hands_requests, goal_id="goal-1",
        steps=[{"kind": "click", "params": {"index": 3}}],
        reversible=False,
    )
    task = memory.tasks()[0]

    decision = RiskPolicy().evaluate(task)

    assert decision.requires_approval is True


def test_default_is_fail_closed_requires_approval_even_with_no_explicit_flags():
    memory = _memory()
    hands_requests = _hands_requests()
    request_hands_action(
        memory, hands_requests, goal_id="goal-1",
        steps=[{"kind": "type_text", "params": {"text": "hello"}}],
    )
    task = memory.tasks()[0]

    decision = RiskPolicy().evaluate(task)

    assert decision.requires_approval is True
    assert "not marked reversible" in decision.reasons
