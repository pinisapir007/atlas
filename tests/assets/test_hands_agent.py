from atlas.assets.hands.agent import HandsAgent
from atlas.brain.models import Task
from atlas.hands.models import HandsRequest
from atlas.hands.registry import HandsRequestRegistry


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeExecutor:
    def __init__(self, outcome=None, error=None):
        self._outcome = outcome
        self._error = error
        self.calls = []

    def execute_steps(self, steps):
        self.calls.append(steps)
        if self._error:
            raise self._error
        return self._outcome


def _registry():
    return HandsRequestRegistry(store=_FakeStore())


def test_run_executes_the_real_correlated_request_via_browser_hands():
    registry = _registry()
    request = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}])
    registry.save_request(request)
    fake_browser = _FakeExecutor(outcome={"results": [{"kind": "navigate", "success": True}], "downloaded_files": []})
    agent = HandsAgent(hands_requests=registry, browser_hands=fake_browser, desktop_hands=_FakeExecutor())

    result = agent.run(task=Task(goal_id="g1", description="d", source_opportunity_id=request.id))

    assert result["status"] == "done"
    assert result["hands_request_id"] == request.id
    assert len(fake_browser.calls) == 1
    saved = registry.get_request(request.id)
    assert saved.status == "done"


def test_run_routes_desktop_steps_to_desktop_hands():
    registry = _registry()
    request = HandsRequest(goal_id="g1", steps=[{"kind": "type_text", "params": {"text": "hi"}}])
    registry.save_request(request)
    fake_desktop = _FakeExecutor(outcome=[{"kind": "type_text", "success": True}])
    agent = HandsAgent(hands_requests=registry, browser_hands=_FakeExecutor(), desktop_hands=fake_desktop)

    result = agent.run(task=Task(goal_id="g1", description="d", source_opportunity_id=request.id))

    assert result["status"] == "done"
    assert len(fake_desktop.calls) == 1


def test_run_with_no_source_opportunity_id_is_honest_not_a_crash():
    agent = HandsAgent(hands_requests=_registry(), browser_hands=_FakeExecutor(), desktop_hands=_FakeExecutor())

    result = agent.run(task=Task(goal_id="g1", description="d"))

    assert result["status"] == "failed"
    assert "no real HandsRequest id" in result["error"]


def test_run_with_an_unknown_request_id_is_honest_not_a_crash():
    agent = HandsAgent(hands_requests=_registry(), browser_hands=_FakeExecutor(), desktop_hands=_FakeExecutor())

    result = agent.run(task=Task(goal_id="g1", description="d", source_opportunity_id="does-not-exist"))

    assert result["status"] == "failed"
    assert "no real HandsRequest found" in result["error"]


def test_run_records_a_real_failure_honestly_never_fabricating_success():
    registry = _registry()
    request = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}])
    registry.save_request(request)
    from atlas.hands.browser_hands import BrowserHandsError

    fake_browser = _FakeExecutor(error=BrowserHandsError("real session crash"))
    agent = HandsAgent(hands_requests=registry, browser_hands=fake_browser, desktop_hands=_FakeExecutor())

    result = agent.run(task=Task(goal_id="g1", description="d", source_opportunity_id=request.id))

    assert result["status"] == "failed"
    assert "real session crash" in result["error"]
    saved = registry.get_request(request.id)
    assert saved.status == "failed"


def test_report_is_a_real_aggregate_over_the_registry():
    registry = _registry()
    r1 = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}], status="done")
    r2 = HandsRequest(goal_id="g1", steps=[{"kind": "navigate", "params": {"url": "u"}}], status="failed")
    registry.save_request(r1)
    registry.save_request(r2)
    agent = HandsAgent(hands_requests=registry, browser_hands=_FakeExecutor(), desktop_hands=_FakeExecutor())

    report = agent.report()

    assert report["total_requests"] == 2
    assert report["done"] == 1
    assert report["failed"] == 1
