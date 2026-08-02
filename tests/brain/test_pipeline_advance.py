from atlas.brain.models import Goal, Task
from atlas.brain.pipeline_advance import advance_recruitment_pipeline
from atlas.core.registry import UnsupportedVerb


class _StubRegistry:
    def __init__(self, report=None, raise_exc=None):
        self._report = report
        self._raise = raise_exc

    def dispatch(self, asset_id, verb):
        if self._raise is not None:
            raise self._raise
        return self._report


class _StubMemory:
    def __init__(self, goal_ids):
        self._goals = [Goal(description=g, id=g) for g in goal_ids]

    def goals(self):
        return self._goals


def _opportunity(stage, goal_id="goal-a", opp_id="opp-1"):
    return {"id": opp_id, "stage": stage, "goal_id": goal_id}


def _report(*opportunities):
    return {"status": "done", "opportunities": list(opportunities)}


def test_creates_task_for_discovered_opportunity():
    registry = _StubRegistry(report=_report(_opportunity("discovered")))
    tasks = advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"]))
    assert len(tasks) == 1
    assert tasks[0].category == "revenue_recruitment_leads"
    assert tasks[0].goal_id == "goal-a"
    assert tasks[0].source_opportunity_id == "opp-1"
    assert tasks[0].reversible is True


def test_creates_task_for_qualified_opportunity():
    registry = _StubRegistry(report=_report(_opportunity("qualified")))
    tasks = advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"]))
    assert len(tasks) == 1


def test_creates_task_for_matched_opportunity():
    registry = _StubRegistry(report=_report(_opportunity("matched")))
    tasks = advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"]))
    assert len(tasks) == 1


def test_no_task_for_proposal_ready_founder_gate():
    registry = _StubRegistry(report=_report(_opportunity("proposal_ready")))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_no_task_for_active_founder_gate():
    registry = _StubRegistry(report=_report(_opportunity("active")))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_no_task_for_won_terminal_stage():
    registry = _StubRegistry(report=_report(_opportunity("won")))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_no_task_for_lost_terminal_stage():
    registry = _StubRegistry(report=_report(_opportunity("lost")))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_no_task_for_untagged_opportunity():
    registry = _StubRegistry(report=_report(_opportunity("discovered", goal_id=None)))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_no_task_for_opportunity_whose_goal_is_not_tracked_by_this_brain():
    # Regression guard: an opportunity can carry a goal_id that belongs to a
    # different brain/environment (e.g. shared registry state). It must never
    # generate a task here just because it has *some* goal_id.
    registry = _StubRegistry(report=_report(_opportunity("discovered", goal_id="goal-elsewhere")))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_no_duplicate_when_open_continuation_task_already_exists():
    registry = _StubRegistry(report=_report(_opportunity("qualified")))
    existing_open = Task(
        goal_id="goal-a",
        description="already in flight",
        category="revenue_recruitment_leads",
        status="proposed",
        source_opportunity_id="opp-1",
    )
    tasks = advance_recruitment_pipeline([existing_open], registry, _StubMemory(["goal-a"]))
    assert tasks == []


def test_new_task_created_once_previous_continuation_task_is_done():
    registry = _StubRegistry(report=_report(_opportunity("matched")))
    resolved = Task(
        goal_id="goal-a",
        description="finished last cycle",
        category="revenue_recruitment_leads",
        status="done",
        source_opportunity_id="opp-1",
    )
    tasks = advance_recruitment_pipeline([resolved], registry, _StubMemory(["goal-a"]))
    assert len(tasks) == 1
    assert tasks[0].source_opportunity_id == "opp-1"


def test_returns_empty_when_recruitment_not_registered():
    registry = _StubRegistry(raise_exc=KeyError("no such asset: recruitment_workforce"))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_returns_empty_when_report_verb_unsupported():
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []


def test_returns_empty_when_report_shape_unrecognized():
    registry = _StubRegistry(report={"status": "done"})  # no "opportunities" key
    assert advance_recruitment_pipeline([], registry, _StubMemory(["goal-a"])) == []

    registry_not_a_dict = _StubRegistry(report="not a dict")
    assert advance_recruitment_pipeline([], registry_not_a_dict, _StubMemory(["goal-a"])) == []


def test_multiple_in_progress_opportunities_each_get_a_task():
    registry = _StubRegistry(
        report=_report(
            _opportunity("discovered", goal_id="goal-a", opp_id="opp-1"),
            _opportunity("matched", goal_id="goal-b", opp_id="opp-2"),
        )
    )
    tasks = advance_recruitment_pipeline([], registry, _StubMemory(["goal-a", "goal-b"]))
    assert {t.source_opportunity_id for t in tasks} == {"opp-1", "opp-2"}
