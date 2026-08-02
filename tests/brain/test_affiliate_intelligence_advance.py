from atlas.brain.affiliate_intelligence_advance import advance_affiliate_intelligence
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.core.registry import UnsupportedVerb


class _StubRegistry:
    def __init__(self, report=None, raise_exc=None):
        self._report = report
        self._raise = raise_exc

    def dispatch(self, asset_id, verb):
        if self._raise is not None:
            raise self._raise
        return self._report


def _opportunity(stage, goal_id="goal-a", opp_id="opp-1", score=0.0, **overrides):
    base = {"id": opp_id, "stage": stage, "goal_id": goal_id, "product_name": "Test Product", "score": score}
    base.update(overrides)
    return base


def _report(*opportunities):
    return {"status": "done", "opportunities": list(opportunities)}


def _memory_with_goal(tmp_path, goal_id="goal-a"):
    memory = BrainMemory(tmp_path / "brain.json")
    memory.save_goal(Goal(description="find affiliate opportunities", id=goal_id))
    return memory


def test_continuation_nudge_for_discovered_or_researched_stage(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    for stage in ("discovered", "researched"):
        registry = _StubRegistry(report=_report(_opportunity(stage)))
        tasks = advance_affiliate_intelligence([], registry, memory, kpis)
        assert len(tasks) == 1
        assert tasks[0].category == "affiliate_intelligence"
        assert tasks[0].reversible is True
        assert tasks[0].source_opportunity_id is None


def test_no_choice_task_when_ranking_is_incomplete_for_the_goal(tmp_path):
    # One ranked, one still researched — not a complete choice yet.
    registry = _StubRegistry(
        report=_report(
            _opportunity("ranked", opp_id="opp-1", score=0.8),
            _opportunity("researched", opp_id="opp-2"),
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_affiliate_intelligence([], registry, memory, kpis)

    # Only the continuation nudge for the still-researched one, no choice task
    assert all(t.source_opportunity_id is None for t in tasks)
    assert not any("Founder choice" in t.description for t in tasks)


def test_one_choice_task_per_ranked_opportunity_once_complete(tmp_path):
    registry = _StubRegistry(
        report=_report(
            _opportunity("ranked", opp_id="opp-1", score=0.8, product_name="Best"),
            _opportunity("ranked", opp_id="opp-2", score=0.1, product_name="Worst"),
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    tasks = advance_affiliate_intelligence([], registry, memory, kpis)

    assert len(tasks) == 2
    assert {t.source_opportunity_id for t in tasks} == {"opp-1", "opp-2"}
    assert all(t.reversible is False for t in tasks)
    # Highest-scored appears first (sorted by score)
    assert "Best" in tasks[0].description


def test_never_requests_choice_twice_for_the_same_opportunity(tmp_path):
    registry = _StubRegistry(report=_report(_opportunity("ranked", score=0.8)))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    already_asked = Task(
        goal_id="goal-a",
        description="already asked",
        category="affiliate_intelligence",
        status="done",
        source_opportunity_id="opp-1",
    )

    tasks = advance_affiliate_intelligence([already_asked], registry, memory, kpis)

    assert tasks == []


def test_records_opportunities_ranked_kpi(tmp_path):
    registry = _StubRegistry(
        report=_report(
            _opportunity("ranked", opp_id="opp-1", score=0.8),
            _opportunity("ranked", opp_id="opp-2", score=0.1),
        )
    )
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    advance_affiliate_intelligence([], registry, memory, kpis)

    assert kpis.latest("opportunities_ranked_goal-a") == 2.0


def test_no_task_for_untagged_or_untracked_goal(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)

    registry = _StubRegistry(report=_report(_opportunity("ranked", goal_id=None)))
    assert advance_affiliate_intelligence([], registry, memory, kpis) == []

    registry = _StubRegistry(report=_report(_opportunity("ranked", goal_id="goal-elsewhere")))
    assert advance_affiliate_intelligence([], registry, memory, kpis) == []


def test_returns_empty_when_asset_not_registered(tmp_path):
    registry = _StubRegistry(raise_exc=KeyError("no such asset"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_affiliate_intelligence([], registry, memory, kpis) == []


def test_returns_empty_when_report_verb_unsupported(tmp_path):
    registry = _StubRegistry(raise_exc=UnsupportedVerb("no report"))
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    assert advance_affiliate_intelligence([], registry, memory, kpis) == []


def test_returns_empty_when_report_shape_unrecognized(tmp_path):
    memory = _memory_with_goal(tmp_path)
    kpis = KPIRegistry(memory)
    registry = _StubRegistry(report={"status": "done"})
    assert advance_affiliate_intelligence([], registry, memory, kpis) == []
