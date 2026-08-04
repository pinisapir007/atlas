"""Business Execution Planning V1 (2026-08-05).

Connects the existing, unmodified Decision Engine (atlas.brain.
decision_engine.decide()) to the three completed engines — Resource
Discovery, Opportunity Discovery, Time Awareness — to produce a
complete, real ExecutionPlan BEFORE any real action. Planning only:
nothing in this module dispatches a Task, calls a Registry asset,
writes to a real external API, publishes anything, or modifies the
filesystem. build_execution_plan() is a pure, read-only function —
same real inputs in, same real ExecutionPlan out, no side effects.

Deliberately named ExecutionPlan is NOT atlas.orchestrator.models.
ExecutionPlan — that class already exists, is already real, tested,
and wired into CEOBrain.tick(), and represents a genuinely different
thing: the live, stateful, step-by-step tracking of one Campaign's
actual execution (verify_readiness -> produce_content ->
request_founder_review -> check_measurement), mutated in place as real
work happens. This module's ExecutionPlan is a read-only planning
artifact — "should ATLAS pursue this, and what would it take" —
produced before any Campaign exists. To avoid the collision this
class is named BusinessExecutionPlan throughout.

Every field of BusinessExecutionPlan is a direct, honest read of an
existing, unmodified real mechanism — nothing here is a new scoring or
evidence model:
- Selected opportunity: opportunity_ranking.rank_opportunities() /
  explain_opportunity_subject() (Opportunity Discovery's own real,
  already-recorded-Finding-based ranking).
- Required resources: decision_engine_integration.check_resources_available()
  (Decision Engine Integration V1, reused verbatim rather than
  reimplemented) against Resource Discovery's real ResourceIndex/
  ResourceAllowlist.
- Estimated execution time: Time Awareness's TimeService/
  calculate_deadline() — real, only when a real duration estimate is
  actually supplied; None (never guessed) otherwise.
- Task dependency order: the real, already-defined
  atlas.orchestrator.models.STEP_KINDS, in the real dependency order
  atlas.orchestrator.orchestrator.start_execution() already builds
  (verify_readiness -> produce_content -> request_founder_review ->
  check_measurement) — described here, never instantiated as real
  ExecutionStep objects (that would require a real, active Campaign,
  which this planning-only module never creates).
- Expected outcome: explain_opportunity()'s real expected_roi/
  probability_of_success — already real-or-None, never fabricated.
- Confidence score: decide()'s own real Decision.confidence.
- Risk assessment: decide()'s real Decision.risks, merged with the
  selected opportunity's own real risks from
  explain_opportunity_subject() — two real, already-computed sources,
  never a new risk model.
- Success criteria: plain, descriptive references to this codebase's
  own already-real measurement mechanisms (kpi_intake.record_manual_
  revenue, cashflow.profit(), the orchestrator's own check_measurement
  step) — not a new scoring mechanism.

can_execute is False, with every real blocking reason listed, unless
the Decision Engine's own real verdict is "invest" AND a real
opportunity has actually been ranked AND every required resource is
real, approved, and indexed. Even when True, this module still never
executes anything — "can" is not "does."
"""

from dataclasses import dataclass, field

from atlas.brain.decision_engine import decide
from atlas.brain.decision_engine_integration import check_resources_available
from atlas.brain.explain import explain_opportunity
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunity_ranking import explain_opportunity_subject, rank_opportunities
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.time_service import TimeService, calculate_deadline
from atlas.orchestrator.models import STEP_KINDS

# The real dependency order atlas.orchestrator.orchestrator.start_execution()
# already builds -- described here for planning purposes, never
# instantiated as real ExecutionStep objects (that needs a real, active
# Campaign, which this planning-only module never creates). Every name
# here is validated against the real, already-defined STEP_KINDS set
# below, so this list can never silently drift from what the real
# orchestrator actually does.
TASK_DEPENDENCY_ORDER = ["verify_readiness", "produce_content", "request_founder_review", "check_measurement"]
assert set(TASK_DEPENDENCY_ORDER) == STEP_KINDS, "TASK_DEPENDENCY_ORDER must name exactly the real orchestrator step kinds"

# Plain, descriptive references to this codebase's own already-real
# measurement mechanisms -- not a new scoring model. Stated once here,
# reused for every plan, since the real success mechanism doesn't
# change per category.
SUCCESS_CRITERIA = [
    "real revenue recorded against the resulting goal (atlas campaign revenue record / kpi_intake.record_manual_revenue)",
    "real, positive profit measured (atlas.brain.cashflow.profit())",
    "the orchestrator's real check_measurement step reaches status=done",
]


@dataclass
class BusinessExecutionPlan:
    """A read-only planning artifact — see this module's own docstring
    for why this is not atlas.orchestrator.models.ExecutionPlan.
    Produced fresh on every call, never persisted, never mutated —
    the same "recompute, nothing is permanently true" discipline
    decide() itself already relies on."""

    category: str
    created_at: str
    verdict: str
    can_execute: bool
    blocking_reasons: list[str]
    selected_opportunity: dict | None
    required_resources: dict
    estimated_execution_time: dict
    task_dependency_order: list[str]
    expected_outcome: dict
    confidence_score: float | None
    risk_assessment: list[str]
    success_criteria: list[str] = field(default_factory=lambda: list(SUCCESS_CRITERIA))


def build_execution_plan(
    category: str,
    knowledge: KnowledgeBase,
    memory: BrainMemory,
    kpis: KPIRegistry,
    resource_index: ResourceIndex | None = None,
    resource_allowlist: ResourceAllowlist | None = None,
    required_resource_paths: list[str] | None = None,
    estimated_duration_seconds: float | None = None,
    time_service: TimeService | None = None,
) -> BusinessExecutionPlan:
    """The one real planning function this module exists for. Pure,
    read-only, no side effects: calls decide() (unmodified, real),
    rank_opportunities()/explain_opportunity_subject() (unmodified,
    real), check_resources_available() (unmodified, real, from
    Decision Engine Integration V1), and TimeService (unmodified, real)
    — combines their real outputs into one BusinessExecutionPlan,
    never inventing evidence any of them didn't already produce.
    """
    resource_index = resource_index if resource_index is not None else ResourceIndex()
    resource_allowlist = resource_allowlist if resource_allowlist is not None else ResourceAllowlist()
    ts = time_service if time_service is not None else TimeService()
    required_resource_paths = required_resource_paths or []

    decision = decide(category, knowledge, memory, kpis)
    category_explanation = explain_opportunity(category, knowledge, memory, kpis)

    ranked = rank_opportunities(category, knowledge)
    selected_opportunity = None
    opportunity_risks: list[str] = []
    if ranked:
        top = ranked[0]
        subject_explanation = explain_opportunity_subject(category, top["subject"], knowledge)
        selected_opportunity = {
            "subject": top["subject"],
            "score": top["score"],
            "recommended_market": top["recommended_market"],
            "independent_sources": top["independent_sources"],
        }
        opportunity_risks = subject_explanation["risks"]

    resources_ok, resource_reason = check_resources_available(required_resource_paths, resource_index, resource_allowlist)
    required_resources = {
        "required_paths": required_resource_paths,
        "available": resources_ok,
        "reason": resource_reason,
    }

    estimated_execution_time = {"duration_seconds": estimated_duration_seconds, "estimated_completion": None}
    if estimated_duration_seconds is not None:
        estimated_execution_time["estimated_completion"] = calculate_deadline(ts.iso_timestamp(), estimated_duration_seconds)

    blocking_reasons: list[str] = []
    if decision.verdict != "invest":
        blocking_reasons.append(f"Decision Engine verdict is '{decision.verdict}', not 'invest': {decision.reasoning}")
    if selected_opportunity is None:
        blocking_reasons.append(f"no real opportunity has been ranked yet for category '{category}'")
    if not resources_ok:
        blocking_reasons.append(resource_reason)

    return BusinessExecutionPlan(
        category=category,
        created_at=ts.iso_timestamp(),
        verdict=decision.verdict,
        can_execute=len(blocking_reasons) == 0,
        blocking_reasons=blocking_reasons,
        selected_opportunity=selected_opportunity,
        required_resources=required_resources,
        estimated_execution_time=estimated_execution_time,
        task_dependency_order=list(TASK_DEPENDENCY_ORDER),
        expected_outcome={"expected_roi": category_explanation["expected_roi"], "probability_of_success": category_explanation["probability_of_success"]},
        confidence_score=decision.confidence,
        risk_assessment=list(dict.fromkeys(decision.risks + opportunity_risks)),  # real risks from both real sources, de-duplicated, order preserved
    )
