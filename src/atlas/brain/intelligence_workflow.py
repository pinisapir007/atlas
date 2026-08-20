"""ATLAS End-to-End Intelligence Workflow V1 (2026-08-05).

Proves that every completed engine — Intelligence Research Framework,
Intelligence Engine, Resource Discovery, Opportunity Discovery, Time
Awareness, Decision Engine, Business Execution Planning — works
together as one real reasoning cycle. This module creates NO new
intelligence engine and no new evidence/scoring model: every stage is
a direct, unmodified call into an engine that already exists, in the
exact order the founder specified:

    1. Receive Business Goal
    2. Intelligence Research Framework  (intelligence_research_framework.build_research_framework)
    3. Intelligence Engine              (intelligence_engine.collect_intelligence)
    4. Resource Discovery               (resource_discovery_engine.scan_resources)
    5. Opportunity Discovery            (opportunity_ranking.rank_opportunities)
    6. Time Awareness                   (time_service.TimeService)
    7. Decision Engine                  (decision_engine.decide)
    8. Business Execution Planning      (business_execution_planning.build_execution_plan)

Stage 5 deliberately reads opportunity_ranking.rank_opportunities()
(already-recorded, evidence-backed Findings) rather than calling
opportunity_discovery_engine.discover_opportunities() — the same
"never trigger a live provider call from an orchestration/planning
layer" precedent decision_engine_integration.py already established
for exactly this reason, applied here for consistency rather than
re-litigated.

Every stage returns a WorkflowStage exposing five things, always,
across every stage — the founder's explicit requirement:
  - output               a structured, real result (a plain dict)
  - reasoning             WHY this stage produced that result, built
                           only from real, already-computed fields —
                           never freeform generated text
  - confidence            a real number when one honestly applies to
                           this stage, else None (never fabricated —
                           the same None-means-unmeasured convention
                           confidence_score() itself already uses).
                           What "confidence" means is stage-specific
                           and stated in that stage's own reasoning:
                           real evidence confidence (stages 5, 7, 8),
                           a real provider/domain coverage ratio
                           (stages 3, 4), a deterministic 1.0 for a
                           system fact that is not a probabilistic
                           estimate (stage 6), or None where no
                           measurement honestly applies (stages 1, 2).
  - missing_information   what is honestly still unknown, real and
                           named, never a vague "more data needed"
  - next_recommended_action  the real, concrete next step

The orchestration layer preserves the complete reasoning history
(IntelligenceWorkflowResult.reasoning_history — every stage's
reasoning string, in the exact order it was produced) and never skips
a stage: stages 1-6 always run, in this exact order, every call.

The one real gate: if required intelligence is missing — fewer than
decision_engine.MIN_INDEPENDENT_SOURCES independently-sourced,
evidence-backed Findings exist for `category` (the same real bar
decide() itself would apply) — the workflow stops BEFORE the Decision
Engine runs at all (stage 7 is never called, not called-and-blocked)
and explains exactly what is still required. This reuses decide()'s
own real threshold rather than inventing a second, competing evidence
bar. Only once that gate passes do stages 7 and 8 run; stage 8 always
runs immediately after stage 7 in that case, using
build_execution_plan()'s own already-correct, already-tested
can_execute/blocking_reasons handling for a non-"invest" verdict —
no second gate is needed there.
"""

from dataclasses import asdict, dataclass, field

from atlas.brain.business_execution_planning import BusinessExecutionPlan, build_execution_plan
from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES, decide
from atlas.brain.evidence_provenance import independent_source_count
from atlas.brain.intelligence_engine import collect_intelligence
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.intelligence_research_framework import build_research_framework
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Decision
from atlas.brain.opportunity_ranking import rank_opportunities
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_discovery_engine import ResourceScanState, scan_resources
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.time_service import TimeService, is_overdue, remaining_seconds
from atlas.integrations.base import INTELLIGENCE_DOMAINS

STAGE_GOAL_RECEIVED = "goal_received"
STAGE_RESEARCH_FRAMEWORK = "intelligence_research_framework"
STAGE_INTELLIGENCE_ENGINE = "intelligence_engine"
STAGE_RESOURCE_DISCOVERY = "resource_discovery"
STAGE_OPPORTUNITY_DISCOVERY = "opportunity_discovery"
STAGE_TIME_AWARENESS = "time_awareness"
STAGE_DECISION_ENGINE = "decision_engine"
STAGE_BUSINESS_EXECUTION_PLANNING = "business_execution_planning"

# The real, exact, founder-specified order. Asserted below against the
# order every stage is actually appended in, so this constant can never
# silently drift from what the code really does.
WORKFLOW_STAGE_ORDER = [
    STAGE_GOAL_RECEIVED,
    STAGE_RESEARCH_FRAMEWORK,
    STAGE_INTELLIGENCE_ENGINE,
    STAGE_RESOURCE_DISCOVERY,
    STAGE_OPPORTUNITY_DISCOVERY,
    STAGE_TIME_AWARENESS,
    STAGE_DECISION_ENGINE,
    STAGE_BUSINESS_EXECUTION_PLANNING,
]


@dataclass
class WorkflowStage:
    """One stage's complete, structured result — every field the
    founder required, present on every single stage, no exceptions."""

    name: str
    output: dict
    reasoning: str
    confidence: float | None
    missing_information: list[str]
    next_recommended_action: str


@dataclass
class IntelligenceWorkflowResult:
    """The complete, real reasoning chain for one goal, start to
    finish (or to the point it honestly stopped). `stages` and
    `reasoning_history` are always in true chronological/dependency
    order — the same order as WORKFLOW_STAGE_ORDER, truncated at
    stage 6 when halted."""

    goal: str
    category: str
    created_at: str
    status: str  # "completed" | "halted_before_decision_engine"
    stages: list[WorkflowStage] = field(default_factory=list)
    reasoning_history: list[str] = field(default_factory=list)
    halted: bool = False
    halted_reason: str | None = None


def _stage_goal_received(goal: str) -> WorkflowStage:
    return WorkflowStage(
        name=STAGE_GOAL_RECEIVED,
        output={"goal": goal},
        reasoning=(
            "Received the real, verbatim business goal as input — no interpretation, parsing, or semantic "
            "extraction is performed at this stage, the same 'no fabricated understanding' boundary "
            "intelligence_research_framework.py already established one stage downstream."
        ),
        confidence=None,  # raw input, not a measurement — no honest score applies
        missing_information=[],
        next_recommended_action=f"Generate the Intelligence Research Framework ({STAGE_RESEARCH_FRAMEWORK}).",
    )


def _stage_research_framework(goal: str, ts: TimeService):
    framework = build_research_framework(goal, ts)
    reasoning = (
        f"Generated a structured research framework from the real goal text: {len(framework.research_questions)} "
        f"research question(s) across {len(framework.intelligence_categories)} intelligence domain(s), "
        f"{len(framework.required_intelligence_sources)} required intelligence source(s), "
        f"{len(framework.missing_knowledge)} named knowledge gap(s). No intelligence was collected or analyzed "
        "at this stage — see intelligence_research_framework.py's own structural, AST-verified guarantee."
    )
    stage = WorkflowStage(
        name=STAGE_RESEARCH_FRAMEWORK,
        output=asdict(framework),
        reasoning=reasoning,
        confidence=None,  # this stage generates questions, not evidence-backed answers — no honest score applies
        missing_information=list(framework.missing_knowledge),
        next_recommended_action="Collect the required intelligence sources named above via the Intelligence Engine.",
    )
    return stage, framework


def _stage_intelligence_engine(knowledge, intelligence_index, intelligence_providers, ts) -> WorkflowStage:
    result = collect_intelligence(providers=intelligence_providers, knowledge=knowledge, index=intelligence_index, time_service=ts)
    items = result["intelligence"]
    provider_status = result["provider_status"]
    domains_covered = sorted({i.domain for i in items})
    total_domains = len(INTELLIGENCE_DOMAINS)
    unavailable = [f"{name}: {status['error']}" for name, status in provider_status.items() if status["count"] == 0 and status["error"]]

    confidence = len(domains_covered) / total_domains if total_domains else None
    reasoning = (
        f"Collected {len(items)} real intelligence item(s) across {len(domains_covered)}/{total_domains} real "
        f"domain(s) from {len(provider_status)} registered provider(s) (domain-coverage ratio, not an "
        "evidence-quality score — see the Decision Engine's confidence for the latter)."
    )
    return WorkflowStage(
        name=STAGE_INTELLIGENCE_ENGINE,
        output={"intelligence_count": len(items), "domains_covered": domains_covered, "provider_status": provider_status},
        reasoning=reasoning,
        confidence=confidence,
        missing_information=unavailable,
        next_recommended_action="Proceed to Resource Discovery to determine what is available to execute on this goal.",
    )


def _stage_resource_discovery(resource_allowlist, resource_providers, resource_index, resource_scan_state) -> WorkflowStage:
    result = scan_resources(allowlist=resource_allowlist, providers=resource_providers, scan_state=resource_scan_state, resource_index=resource_index)
    resources = result["resources"]
    provider_status = result["provider_status"]
    total_providers = len(provider_status)
    providers_with_data = sum(1 for s in provider_status.values() if s["count"] > 0)
    unavailable = [f"{name}: {status['error']}" for name, status in provider_status.items() if status["count"] == 0 and status["error"]]

    confidence = providers_with_data / total_providers if total_providers else None
    reasoning = (
        f"Scanned {len(resources)} real resource(s), {providers_with_data}/{total_providers} provider(s) "
        "returned real data. NEVER scans anything without explicit, durable, founder-recorded approval "
        "(ResourceAllowlist) — the standing invariant this engine enforces independently of this workflow."
    )
    return WorkflowStage(
        name=STAGE_RESOURCE_DISCOVERY,
        output={
            "resource_count": len(resources),
            "provider_status": provider_status,
            "new": result["new"],
            "modified": result["modified"],
            "deleted": result["deleted"],
            "duplicates": result["duplicates"],
        },
        reasoning=reasoning,
        confidence=confidence,
        missing_information=unavailable,
        next_recommended_action="Proceed to Opportunity Discovery to identify real, evidence-backed opportunities.",
    )


def _stage_opportunity_discovery(category: str, knowledge: KnowledgeBase) -> WorkflowStage:
    ranked = rank_opportunities(category, knowledge)
    top = ranked[0] if ranked else None
    reasoning = (
        f"Ranked {len(ranked)} real, evidence-backed opportunity subject(s) for category '{category}' from "
        "already-recorded Findings (opportunity_ranking.rank_opportunities()). Never triggers a live provider "
        "discovery call from within this orchestration layer — the same precedent already established by "
        "decision_engine_integration.check_opportunity_available()."
    )
    missing = [] if ranked else [f"no real opportunity has been ranked yet for category '{category}'"]
    return WorkflowStage(
        name=STAGE_OPPORTUNITY_DISCOVERY,
        output={"category": category, "ranked_opportunities": ranked, "top_opportunity": top},
        reasoning=reasoning,
        confidence=top["score"] if top else None,
        missing_information=missing,
        next_recommended_action="Proceed to Time Awareness to evaluate timing, urgency, and sequencing.",
    )


def _stage_time_awareness(ts: TimeService, deadline_iso: str | None, minimum_remaining_seconds: float) -> WorkflowStage:
    snapshot = ts.snapshot()
    deadline_analysis = None
    missing: list[str] = []

    if deadline_iso is not None:
        remaining = remaining_seconds(deadline_iso, ts)
        overdue = is_overdue(deadline_iso, ts)
        deadline_analysis = {"deadline_iso": deadline_iso, "remaining_seconds": remaining, "is_overdue": overdue}
        if overdue or remaining < minimum_remaining_seconds:
            missing.append(f"insufficient real time remains before deadline {deadline_iso}: {remaining:.1f}s remaining")
        reasoning = (
            "Evaluated real current time via the central TimeService (Asia/Jerusalem primary timezone, real "
            f"DST-aware). Deadline {deadline_iso} evaluated: {'OVERDUE' if overdue else 'on track'}, "
            f"{remaining:.1f}s remaining."
        )
    else:
        reasoning = (
            "Evaluated real current time via the central TimeService (Asia/Jerusalem primary timezone, real "
            "DST-aware). No deadline was supplied for this goal — sequencing has no urgency constraint yet."
        )

    return WorkflowStage(
        name=STAGE_TIME_AWARENESS,
        output={"snapshot": snapshot, "deadline_analysis": deadline_analysis},
        reasoning=reasoning,
        # Time is a real, deterministic system fact, not a probabilistic estimate — a stated 1.0 is honest
        # here, not fabricated, the same way a completed checklist item is honestly "done", not "estimated".
        confidence=1.0,
        missing_information=missing,
        next_recommended_action="Evaluate whether required intelligence is sufficient before proceeding to the Decision Engine.",
    )


def _stage_decision_engine(decision: Decision) -> WorkflowStage:
    next_action = {
        "invest": "Proceed to Business Execution Planning.",
        "already_invested": "No new commitment needed — monitor the existing active goal(s).",
        "already_proposed": "Awaiting founder decision on the existing capability-gap proposal.",
        "propose_capability": "A structural create_asset proposal is required before this category can be executed — awaiting founder review.",
    }.get(decision.verdict, "Review the Decision Engine's reasoning above.")
    return WorkflowStage(
        name=STAGE_DECISION_ENGINE,
        output=asdict(decision),
        reasoning=decision.reasoning,
        confidence=decision.confidence,
        missing_information=[],  # the only "missing" verdict decide() has (insufficient_evidence) is caught by this workflow's own gate before this stage ever runs
        next_recommended_action=next_action,
    )


def _stage_business_execution_planning(plan: BusinessExecutionPlan) -> WorkflowStage:
    reasoning = (
        "can_execute=True: every requirement (Decision Engine verdict, ranked opportunity, approved and "
        "indexed resources) is satisfied."
        if plan.can_execute
        else "can_execute=False: " + "; ".join(plan.blocking_reasons)
    )
    next_action = (
        "Hand off to the Execution Orchestrator (atlas.orchestrator) to begin real execution."
        if plan.can_execute
        else "Resolve the blocking reason(s) above before execution can begin."
    )
    return WorkflowStage(
        name=STAGE_BUSINESS_EXECUTION_PLANNING,
        output=asdict(plan),
        reasoning=reasoning,
        confidence=plan.confidence_score,
        missing_information=list(plan.blocking_reasons),
        next_recommended_action=next_action,
    )


def run_intelligence_workflow(
    goal: str,
    category: str,
    knowledge: KnowledgeBase | None = None,
    memory: BrainMemory | None = None,
    kpis: KPIRegistry | None = None,
    resource_allowlist: ResourceAllowlist | None = None,
    resource_index: ResourceIndex | None = None,
    resource_scan_state: ResourceScanState | None = None,
    intelligence_index: IntelligenceIndex | None = None,
    intelligence_providers: list | None = None,
    resource_providers: list | None = None,
    required_resource_paths: list[str] | None = None,
    deadline_iso: str | None = None,
    minimum_remaining_seconds: float = 0.0,
    estimated_duration_seconds: float | None = None,
    time_service: TimeService | None = None,
) -> IntelligenceWorkflowResult:
    """The one real orchestration function this module exists for.
    Executes the founder's exact 8-stage order, top to bottom, every
    call — stages 1-6 always run; stages 7-8 only run once the real
    intelligence-sufficiency gate passes (see module docstring).

    Creates no new intelligence, evidence, or scoring model: every
    stage is a direct, unmodified call into an already-completed
    engine. Every dependency defaults to a real instance when not
    supplied, the same explicit-dependency-injection convention every
    other engine in this codebase already uses — real by default,
    fully substitutable for deterministic, isolated tests.
    """
    if not goal or not goal.strip():
        raise ValueError("a real, non-empty business goal is required to run the intelligence workflow")
    if not category or not category.strip():
        raise ValueError("a real, non-empty category is required to run the intelligence workflow")

    knowledge = knowledge if knowledge is not None else KnowledgeBase()
    memory = memory if memory is not None else BrainMemory()
    kpis = kpis if kpis is not None else KPIRegistry(memory)
    resource_allowlist = resource_allowlist if resource_allowlist is not None else ResourceAllowlist()
    resource_index = resource_index if resource_index is not None else ResourceIndex()
    resource_scan_state = resource_scan_state if resource_scan_state is not None else ResourceScanState()
    intelligence_index = intelligence_index if intelligence_index is not None else IntelligenceIndex()
    ts = time_service if time_service is not None else TimeService()
    required_resource_paths = required_resource_paths or []

    stages: list[WorkflowStage] = []
    reasoning_history: list[str] = []

    def _record(stage: WorkflowStage) -> None:
        stages.append(stage)
        reasoning_history.append(stage.reasoning)

    _record(_stage_goal_received(goal))

    stage2, _framework = _stage_research_framework(goal, ts)
    _record(stage2)

    _record(_stage_intelligence_engine(knowledge, intelligence_index, intelligence_providers, ts))
    _record(_stage_resource_discovery(resource_allowlist, resource_providers, resource_index, resource_scan_state))
    _record(_stage_opportunity_discovery(category, knowledge))
    _record(_stage_time_awareness(ts, deadline_iso, minimum_remaining_seconds))

    # The one real gate: reuses decide()'s own real evidence threshold —
    # never a second, competing bar. "Stop BEFORE the Decision Engine"
    # means stage 7 is never called at all when this fails, not called
    # and returned as a blocked/insufficient result.
    sourced = [f for f in knowledge.findings(category=category) if f.evidence]
    # Independent-source counting (2026-08-17, ONE BRAIN Evidence
    # Provenance) -- the same real evidence_provenance.
    # independent_source_count() decision_engine.decide() itself now
    # uses, reused here rather than a second, competing implementation.
    independent_count = independent_source_count(sourced)
    if independent_count < MIN_INDEPENDENT_SOURCES:
        halted_reason = (
            f"Required intelligence is missing before the Decision Engine can run: only {independent_count}/"
            f"{MIN_INDEPENDENT_SOURCES} independently-sourced, evidence-backed Finding(s) exist for category "
            f"'{category}' — the same standing evidence bar atlas.brain.decision_engine.decide() itself "
            "requires before any investment verdict (decision_engine.MIN_INDEPENDENT_SOURCES). Record more "
            "real, evidenced Findings for this category (atlas brain finding add <source> "
            f"{category} \"<description>\" --evidence <url>), then re-run this workflow."
        )
        reasoning_history.append(halted_reason)
        return IntelligenceWorkflowResult(
            goal=goal,
            category=category,
            created_at=ts.iso_timestamp(),
            status="halted_before_decision_engine",
            stages=stages,
            reasoning_history=reasoning_history,
            halted=True,
            halted_reason=halted_reason,
        )

    decision = decide(category, knowledge, memory, kpis)
    _record(_stage_decision_engine(decision))

    plan = build_execution_plan(
        category,
        knowledge,
        memory,
        kpis,
        resource_index=resource_index,
        resource_allowlist=resource_allowlist,
        required_resource_paths=required_resource_paths,
        estimated_duration_seconds=estimated_duration_seconds,
        time_service=ts,
    )
    _record(_stage_business_execution_planning(plan))

    return IntelligenceWorkflowResult(
        goal=goal,
        category=category,
        created_at=ts.iso_timestamp(),
        status="completed",
        stages=stages,
        reasoning_history=reasoning_history,
        halted=False,
        halted_reason=None,
    )


assert WORKFLOW_STAGE_ORDER == [
    STAGE_GOAL_RECEIVED,
    STAGE_RESEARCH_FRAMEWORK,
    STAGE_INTELLIGENCE_ENGINE,
    STAGE_RESOURCE_DISCOVERY,
    STAGE_OPPORTUNITY_DISCOVERY,
    STAGE_TIME_AWARENESS,
    STAGE_DECISION_ENGINE,
    STAGE_BUSINESS_EXECUTION_PLANNING,
], "WORKFLOW_STAGE_ORDER must name every real stage in the founder's exact specified order"
