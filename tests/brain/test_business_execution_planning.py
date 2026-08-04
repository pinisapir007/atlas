import pytest

from atlas.brain.business_execution_planning import (
    SUCCESS_CRITERIA,
    TASK_DEPENDENCY_ORDER,
    build_execution_plan,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_index import ResourceIndex
from atlas.integrations.base import Resource


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


def _sourced_finding(category: str, i: int, subject: str = "") -> Finding:
    return Finding(source="research", category=category, description=f"signal {i}", evidence=f"https://example.com/{i}", subject=subject)


def test_plan_is_not_executable_with_insufficient_evidence(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))  # only one source -- below MIN_INDEPENDENT_SOURCES
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.can_execute is False
    assert plan.verdict == "insufficient_evidence"
    assert any("insufficient_evidence" in r for r in plan.blocking_reasons)


def test_plan_is_not_executable_without_a_ranked_opportunity_even_with_a_real_invest_verdict(tmp_path):
    kb = _kb(tmp_path)
    # Two category-general sourced findings (no subject) -> a real
    # "invest" verdict, but rank_opportunities() only ranks findings
    # that name a real subject, so nothing is ranked here.
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.verdict == "invest"
    assert plan.selected_opportunity is None
    assert plan.can_execute is False
    assert any("no real opportunity" in r for r in plan.blocking_reasons)


def test_plan_selects_the_real_top_ranked_opportunity_when_one_exists(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.selected_opportunity is not None
    assert plan.selected_opportunity["subject"] == "Widget"


def test_plan_blocks_on_a_required_resource_that_is_not_approved(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan(
        "digital_product", kb, memory, kpis,
        resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()),
        required_resource_paths=["/not/approved.txt"],
    )

    assert plan.can_execute is False
    assert plan.required_resources["available"] is False
    assert any("not approved" in r for r in plan.blocking_reasons)


def test_plan_is_fully_executable_when_verdict_opportunity_and_resources_all_line_up(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder("/approved")
    resource_index = ResourceIndex(store=_FakeStore())
    resource_index.replace_index([Resource(provider="local_folder", path="/approved/brief.txt", resource_type="file")])

    plan = build_execution_plan(
        "digital_product", kb, memory, kpis,
        resource_index=resource_index, resource_allowlist=allowlist,
        required_resource_paths=["/approved/brief.txt"],
    )

    assert plan.can_execute is True
    assert plan.blocking_reasons == []
    assert plan.verdict == "invest"


def test_confidence_score_is_the_real_decision_confidence(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.confidence_score is not None
    assert 0.0 <= plan.confidence_score <= 1.0


def test_expected_outcome_is_honestly_none_with_no_real_revenue_data(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.expected_outcome["expected_roi"] is None  # no real goal/revenue exists yet -- never fabricated
    assert plan.expected_outcome["probability_of_success"] is None


def test_estimated_execution_time_stays_unset_without_a_real_duration_supplied(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.estimated_execution_time == {"duration_seconds": None, "estimated_completion": None}


def test_estimated_execution_time_computes_a_real_completion_when_a_duration_is_supplied(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan(
        "digital_product", kb, memory, kpis,
        resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()),
        estimated_duration_seconds=3600,
    )

    assert plan.estimated_execution_time["duration_seconds"] == 3600
    assert plan.estimated_execution_time["estimated_completion"] is not None


def test_task_dependency_order_matches_the_real_orchestrator_step_order(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.task_dependency_order == TASK_DEPENDENCY_ORDER
    assert plan.task_dependency_order == ["verify_readiness", "produce_content", "request_founder_review", "check_measurement"]


def test_success_criteria_are_the_real_stated_criteria(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert plan.success_criteria == SUCCESS_CRITERIA


def test_risk_assessment_merges_decision_and_opportunity_risks_without_duplicates(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    plan = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert isinstance(plan.risk_assessment, list)
    assert len(plan.risk_assessment) == len(set(plan.risk_assessment))  # no duplicates


def test_build_execution_plan_never_mutates_or_persists_anything(tmp_path):
    # Purely a planning read: calling it twice with the same real inputs
    # must not change knowledge/memory/kpis state at all.
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    findings_before = len(kb.findings())
    goals_before = len(memory.goals())

    build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))
    build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert len(kb.findings()) == findings_before
    assert len(memory.goals()) == goals_before


def test_plan_is_deterministic_given_the_same_real_inputs(tmp_path):
    # "Deterministic" here means the same real evidence always produces
    # the same real structural verdict -- not that two calls separated
    # by real wall-clock time produce a bit-identical confidence score.
    # confidence_score()'s recency factor decays continuously with real
    # elapsed time (documented, intentional behavior), so the score
    # itself can differ by a tiny, real amount between two calls a few
    # microseconds apart -- that's correct, not a determinism bug.
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1, subject="Widget"))
    kb.save_finding(_sourced_finding("digital_product", 2, subject="Widget"))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    first = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))
    second = build_execution_plan("digital_product", kb, memory, kpis, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()))

    assert first.verdict == second.verdict
    assert first.can_execute == second.can_execute
    assert first.selected_opportunity["subject"] == second.selected_opportunity["subject"]
    assert first.confidence_score == pytest.approx(second.confidence_score, abs=1e-6)
