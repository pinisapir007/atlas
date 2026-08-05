import ast
import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.intelligence_workflow import (
    STAGE_BUSINESS_EXECUTION_PLANNING,
    STAGE_DECISION_ENGINE,
    STAGE_GOAL_RECEIVED,
    STAGE_INTELLIGENCE_ENGINE,
    STAGE_OPPORTUNITY_DISCOVERY,
    STAGE_RESEARCH_FRAMEWORK,
    STAGE_RESOURCE_DISCOVERY,
    STAGE_TIME_AWARENESS,
    WORKFLOW_STAGE_ORDER,
    WorkflowStage,
    run_intelligence_workflow,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_discovery_engine import ResourceScanState
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.time_service import TimeService

_REALISTIC_GOAL = "Become the best Affiliate Marketing business"
_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _deps():
    """Every real dependency this workflow can take, fully isolated —
    the same _FakeStore()-per-registry discipline every other engine's
    test suite in this codebase already establishes. Never touches
    this project's real .atlas/ state."""
    memory = BrainMemory(store=_FakeStore())
    return {
        "knowledge": KnowledgeBase(store=_FakeStore()),
        "memory": memory,
        "kpis": KPIRegistry(memory),
        "resource_allowlist": ResourceAllowlist(store=_FakeStore()),
        "resource_index": ResourceIndex(store=_FakeStore()),
        "resource_scan_state": ResourceScanState(store=_FakeStore()),
        "intelligence_index": IntelligenceIndex(store=_FakeStore()),
        "time_service": TimeService(clock=lambda: _NOW),
    }


def _seed_sufficient_evidence(knowledge: KnowledgeBase, category: str = "affiliate", subject: str = "KetoDNA"):
    knowledge.save_finding(Finding(source="research", category=category, description="real evidence 1", evidence="https://example.com/1", subject=subject, market="US"))
    knowledge.save_finding(Finding(source="research", category=category, description="real evidence 2", evidence="https://example.com/2", subject=subject, market="US"))


def test_end_to_end_reasoning_chain_for_become_the_best_affiliate_marketing_business():
    # The founder's exact required integration test: a realistic goal,
    # verifying the complete real reasoning chain end to end.
    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"], category="affiliate")

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    assert result.goal == _REALISTIC_GOAL
    assert result.category == "affiliate"
    assert result.status == "completed"
    assert result.halted is False
    assert result.halted_reason is None
    assert [s.name for s in result.stages] == WORKFLOW_STAGE_ORDER
    assert len(result.stages) == 8

    # Stage 1: the real, verbatim goal, uninterpreted.
    assert result.stages[0].output["goal"] == _REALISTIC_GOAL

    # Stage 2: a real research framework grounded in the real goal text.
    framework_output = result.stages[1].output
    assert framework_output["objective"] == _REALISTIC_GOAL
    assert len(framework_output["research_questions"]) == 5

    # Stage 5: a real, ranked opportunity for the seeded subject.
    opportunity_output = result.stages[4].output
    assert opportunity_output["top_opportunity"]["subject"] == "KetoDNA"

    # Stage 7: a real Decision Engine verdict, never fabricated.
    decision_output = result.stages[6].output
    assert decision_output["category"] == "affiliate"
    assert decision_output["verdict"] in {"invest", "already_invested", "already_proposed", "propose_capability"}

    # Stage 8: a real, read-only Business Execution Plan.
    plan_output = result.stages[7].output
    assert plan_output["category"] == "affiliate"
    assert isinstance(plan_output["can_execute"], bool)

    # The complete reasoning history is preserved, one entry per stage, in order.
    assert result.reasoning_history == [s.reasoning for s in result.stages]


def test_halts_before_decision_engine_when_required_intelligence_is_missing():
    deps = _deps()  # zero findings seeded -- required intelligence is genuinely missing

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    assert result.status == "halted_before_decision_engine"
    assert result.halted is True
    assert result.halted_reason is not None
    assert "affiliate" in result.halted_reason
    assert "0/2" in result.halted_reason

    # Stages 1-6 ran; the Decision Engine and Business Execution Planning never did.
    assert [s.name for s in result.stages] == WORKFLOW_STAGE_ORDER[:6]
    assert STAGE_DECISION_ENGINE not in [s.name for s in result.stages]
    assert STAGE_BUSINESS_EXECUTION_PLANNING not in [s.name for s in result.stages]

    # The halt reason is the final entry in the preserved reasoning history.
    assert result.reasoning_history[-1] == result.halted_reason
    assert len(result.reasoning_history) == 7  # 6 real stage reasons + the halt explanation


def test_halts_with_only_one_independently_sourced_finding():
    # One real, evidenced finding is still below MIN_INDEPENDENT_SOURCES (2).
    deps = _deps()
    deps["knowledge"].save_finding(Finding(source="research", category="affiliate", description="only one", evidence="https://example.com/1", subject="KetoDNA"))

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    assert result.status == "halted_before_decision_engine"
    assert "1/2" in result.halted_reason


def test_nothing_may_skip_stages_the_order_constant_is_the_founders_exact_order():
    assert WORKFLOW_STAGE_ORDER == [
        STAGE_GOAL_RECEIVED,
        STAGE_RESEARCH_FRAMEWORK,
        STAGE_INTELLIGENCE_ENGINE,
        STAGE_RESOURCE_DISCOVERY,
        STAGE_OPPORTUNITY_DISCOVERY,
        STAGE_TIME_AWARENESS,
        STAGE_DECISION_ENGINE,
        STAGE_BUSINESS_EXECUTION_PLANNING,
    ]


def test_every_stage_exposes_all_five_required_fields():
    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"])
    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    field_names = {f.name for f in dataclasses.fields(WorkflowStage)}
    assert field_names == {"name", "output", "reasoning", "confidence", "missing_information", "next_recommended_action"}

    for stage in result.stages:
        assert isinstance(stage.output, dict) and stage.output
        assert isinstance(stage.reasoning, str) and stage.reasoning
        assert stage.confidence is None or isinstance(stage.confidence, (int, float))
        assert isinstance(stage.missing_information, list)
        assert isinstance(stage.next_recommended_action, str) and stage.next_recommended_action


def test_raises_on_an_empty_goal():
    deps = _deps()
    with pytest.raises(ValueError, match="non-empty business goal"):
        run_intelligence_workflow("", "affiliate", **deps)


def test_raises_on_an_empty_category():
    deps = _deps()
    with pytest.raises(ValueError, match="non-empty category"):
        run_intelligence_workflow(_REALISTIC_GOAL, "   ", **deps)


def test_the_workflow_creates_no_new_finding_itself():
    # Every stage here reads already-existing engines' real, already-
    # tested behavior -- this orchestration layer must never fabricate
    # or silently create new evidence of its own.
    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"])
    before = len(deps["knowledge"].findings())

    run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    assert len(deps["knowledge"].findings()) == before


def test_time_awareness_confidence_is_a_deterministic_1_point_0():
    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"])
    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    time_stage = next(s for s in result.stages if s.name == STAGE_TIME_AWARENESS)
    assert time_stage.confidence == 1.0


def test_time_awareness_reports_an_overdue_deadline_as_missing_information():
    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"])
    past_deadline = (_NOW - timedelta(hours=1)).isoformat()

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", deadline_iso=past_deadline, **deps)

    time_stage = next(s for s in result.stages if s.name == STAGE_TIME_AWARENESS)
    assert time_stage.output["deadline_analysis"]["is_overdue"] is True
    assert any("insufficient" in m for m in time_stage.missing_information)
    assert "OVERDUE" in time_stage.reasoning


def test_intelligence_engine_stage_confidence_is_a_real_domain_coverage_ratio():
    from atlas.integrations.base import Intelligence

    class _FakeIntelligenceProvider:
        def __init__(self, name, domain, item):
            self.name = name
            self.domain = domain
            self._item = item

        def fetch_intelligence(self):
            return [self._item] if self._item else []

    providers = [
        _FakeIntelligenceProvider("market_provider", "market", Intelligence(provider="market_provider", domain="market", subject="X", summary="real")),
        _FakeIntelligenceProvider("competitor_provider", "competitor", Intelligence(provider="competitor_provider", domain="competitor", subject="Y", summary="real")),
        _FakeIntelligenceProvider("silent_provider", "human_behavior", None),
    ]

    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"])
    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", intelligence_providers=providers, **deps)

    stage = next(s for s in result.stages if s.name == STAGE_INTELLIGENCE_ENGINE)
    # 2 real domains covered (market, competitor) out of 5 total real Intelligence Engine domains.
    assert stage.confidence == pytest.approx(2 / 5)
    assert stage.output["domains_covered"] == ["competitor", "market"]


def test_resource_discovery_never_scans_without_explicit_approval():
    deps = _deps()  # empty ResourceAllowlist -- nothing approved
    _seed_sufficient_evidence(deps["knowledge"])

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)

    stage = next(s for s in result.stages if s.name == STAGE_RESOURCE_DISCOVERY)
    assert stage.output["resource_count"] == 0
    assert any("local_folder" in m for m in stage.missing_information)


def test_business_execution_plan_stage_output_matches_a_direct_real_call():
    from atlas.brain.business_execution_planning import build_execution_plan

    deps = _deps()
    _seed_sufficient_evidence(deps["knowledge"])

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate", **deps)
    stage_output = next(s for s in result.stages if s.name == STAGE_BUSINESS_EXECUTION_PLANNING).output

    direct_plan = build_execution_plan(
        "affiliate",
        deps["knowledge"],
        deps["memory"],
        deps["kpis"],
        resource_index=deps["resource_index"],
        resource_allowlist=deps["resource_allowlist"],
        time_service=deps["time_service"],
    )

    assert stage_output["can_execute"] == direct_plan.can_execute
    assert stage_output["verdict"] == direct_plan.verdict
    # recency_score() decays continuously against real wall-clock time
    # regardless of the injected TimeService (the same non-bug already
    # documented for confidence-score determinism elsewhere in this
    # codebase's test suite) -- compare structurally, score via approx.
    assert stage_output["selected_opportunity"]["subject"] == direct_plan.selected_opportunity["subject"]
    assert stage_output["selected_opportunity"]["score"] == pytest.approx(direct_plan.selected_opportunity["score"])
    assert stage_output["blocking_reasons"] == direct_plan.blocking_reasons


def test_does_not_import_a_live_opportunity_discovery_call():
    # Structural, not just documentary: this module must never import
    # discover_opportunities (which would trigger live provider network
    # calls from inside a planning/orchestration layer) -- the same
    # AST-based, docstring-immune proof intelligence_research_framework.py
    # already established for its own no-collection guarantee.
    module_path = Path(__file__).resolve().parents[2] / "src" / "atlas" / "brain" / "intelligence_workflow.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)

    assert "discover_opportunities" not in imported_names


def test_never_writes_outside_an_isolated_working_directory(tmp_path, monkeypatch):
    # Every dependency left at its real default still only ever touches
    # files under the current working directory's .atlas/ -- chdir into
    # an empty tmp_path first, so a real repository's .atlas/ state is
    # never at risk even when no explicit store is injected.
    monkeypatch.chdir(tmp_path)

    knowledge = KnowledgeBase()  # real default path, now relative to tmp_path
    _seed_sufficient_evidence(knowledge)

    result = run_intelligence_workflow(_REALISTIC_GOAL, "affiliate")

    assert result.status == "completed"
    created = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert created  # real files were written (indexes/scan state) -- but only inside tmp_path
    assert all(name.startswith(".atlas/") for name in created)
