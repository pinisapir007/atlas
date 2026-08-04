"""Decision Engine Integration V1 (2026-08-05).

Wires the three completed engines — Resource Discovery, Opportunity
Discovery, Time Awareness — into one deterministic, explainable
EXECUTE/WAIT verdict for a specific task. Deliberately NOT
atlas.brain.decision_engine (decide()/Decision/DecisionLog): that
module answers a different question at a different scope — "is a
whole category worth investing in, given evidence" — and is untouched
by this file, not imported, not renamed, not extended. This module
answers a narrower, task-level question: "can this specific task
actually execute right now, given what's really available." Two real,
separate decisions, two real, separate modules — the same discipline
this codebase already applies everywhere two genuinely different
concepts share a similar name (e.g. Campaign vs. AffiliateOpportunity).

Reads every engine's already-produced state, never re-triggers any of
them:
- Resource Discovery: ResourceIndex.get_resource() (already-scanned
  data) + ResourceAllowlist.is_approved() (defense in depth, the same
  multi-layer-must-agree discipline Resource Discovery itself already
  established) — never a new scan.
- Opportunity Discovery: opportunity_ranking.rank_opportunities() —
  reads real, already-recorded Findings from KnowledgeBase, the exact
  function `atlas brain opportunities` already uses. Never calls
  discover_opportunities() (which would trigger live provider calls);
  never fabricates a ranked opportunity when none exists.
- Time Awareness: every real-time read goes through TimeService,
  exclusively via time_service.remaining_seconds() — no bare
  datetime.now() anywhere in this module.

Task itself is completely untouched — no new fields, no changed
behavior. What a task requires to execute (resource paths, an
opportunity category, a deadline) is expressed as an explicit,
separate TaskExecutionRequirements object, supplied by the caller —
the same "the subject stays what it is; what's required is a separate,
explicit input" pattern this codebase already uses elsewhere (e.g.
brand.factory's BrandDraft never stored on Campaign; ExecutionStep's
own result is separate from the Task it correlates to).

Deterministic and explainable by construction: three independent, pure
check functions (check_resources_available, check_opportunity_available,
check_time_remaining), each returning (passed, reason) — no hidden
state, no partial credit, no scoring blend. EXECUTE only when all three
pass; otherwise WAIT, with every failing check's exact reason
collected, never just the first one found.
"""

from dataclasses import dataclass, field

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Task
from atlas.brain.opportunity_ranking import rank_opportunities
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.time_service import TimeService, remaining_seconds

EXECUTE = "EXECUTE"
WAIT = "WAIT"


@dataclass
class TaskExecutionRequirements:
    """What must be real and true for one specific task to be allowed
    to execute — an explicit, separate input contract, never stored on
    Task itself. Every field left at its default means "no requirement
    on this axis" — the same graceful-absence handling every check
    function below applies consistently: an unset requirement always
    passes, it never blocks by default."""

    required_resource_paths: list[str] = field(default_factory=list)
    opportunity_category: str | None = None
    min_opportunity_confidence: float | None = None
    deadline_iso: str | None = None
    minimum_remaining_seconds: float = 0.0


@dataclass
class ExecutionReadiness:
    """The real, deterministic verdict for one task evaluation —
    EXECUTE or WAIT, with every blocking reason (never just the first)
    and a per-check breakdown for explainability."""

    task_id: str
    decision: str  # EXECUTE | WAIT
    reasons: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


def check_resources_available(
    required_paths: list[str], resource_index: ResourceIndex, resource_allowlist: ResourceAllowlist
) -> tuple[bool, str | None]:
    """Every required resource path must be both (a) explicitly
    founder-approved right now (ResourceAllowlist.is_approved() — an
    approval can be revoked after a resource was indexed, so this is
    checked fresh, not assumed from the index alone) and (b) actually
    present in the already-scanned ResourceIndex with no real scan
    error. Never triggers a new scan — reads only what Resource
    Discovery already found. No required paths means no requirement on
    this axis: passes trivially."""
    for path in required_paths:
        if not resource_allowlist.is_approved(path):
            return False, f"resource not approved: {path}"
        resource = resource_index.get_resource(path)
        if resource is None:
            return False, f"resource not found in the index (never scanned, or since removed): {path}"
        if resource.error:
            return False, f"resource has a real scan error, not usable: {path} ({resource.error})"
    return True, None


def check_opportunity_available(
    category: str | None, knowledge: KnowledgeBase, min_confidence: float | None = None
) -> tuple[bool, str | None]:
    """At least one real, evidence-backed opportunity must be on record
    for `category`, per opportunity_ranking.rank_opportunities() — reads
    already-recorded real Findings, never triggers a live discovery
    call, never fabricates a candidate when none exists. No category
    given means no requirement on this axis: passes trivially."""
    if category is None:
        return True, None
    ranked = rank_opportunities(category, knowledge)
    if not ranked:
        return False, f"no real opportunity recorded for category '{category}'"
    top_score = ranked[0]["score"]
    if top_score is None:
        return False, f"the top-ranked opportunity for '{category}' has no real evidence-based score yet"
    if min_confidence is not None and top_score < min_confidence:
        return False, f"the top-ranked opportunity for '{category}' scores {top_score:.3f}, below the required minimum {min_confidence:.3f}"
    return True, None


def check_time_remaining(
    deadline_iso: str | None, minimum_seconds: float, time_service: TimeService | None = None
) -> tuple[bool, str | None]:
    """At least `minimum_seconds` of real time must remain before
    `deadline_iso`, measured exclusively through TimeService (never
    datetime.now() directly). No deadline given means no requirement on
    this axis: passes trivially."""
    if deadline_iso is None:
        return True, None
    remaining = remaining_seconds(deadline_iso, time_service)
    if remaining < minimum_seconds:
        return False, f"only {remaining:.1f}s remain before deadline {deadline_iso}, need at least {minimum_seconds:.1f}s"
    return True, None


def evaluate_task_readiness(
    task: Task,
    requirements: TaskExecutionRequirements,
    resource_index: ResourceIndex | None = None,
    resource_allowlist: ResourceAllowlist | None = None,
    knowledge: KnowledgeBase | None = None,
    time_service: TimeService | None = None,
) -> ExecutionReadiness:
    """The one real combinator: runs all three checks independently
    (every one always runs — a caller never sees a check silently
    skipped because an earlier one already failed), and returns EXECUTE
    only if every check passed. Otherwise WAIT, with every failing
    check's exact reason collected, not just the first.

    Every dependency defaults to a real instance when not supplied,
    matching the explicit-dependency-injection convention every other
    engine in this codebase already uses (CEOBrain's own constructor,
    for one) — real by default, fully substitutable for deterministic
    tests.
    """
    resource_index = resource_index if resource_index is not None else ResourceIndex()
    resource_allowlist = resource_allowlist if resource_allowlist is not None else ResourceAllowlist()
    knowledge = knowledge if knowledge is not None else KnowledgeBase()

    resources_ok, resource_reason = check_resources_available(requirements.required_resource_paths, resource_index, resource_allowlist)
    opportunity_ok, opportunity_reason = check_opportunity_available(requirements.opportunity_category, knowledge, requirements.min_opportunity_confidence)
    time_ok, time_reason = check_time_remaining(requirements.deadline_iso, requirements.minimum_remaining_seconds, time_service)

    checks = {
        "resources": {"passed": resources_ok, "reason": resource_reason},
        "opportunity": {"passed": opportunity_ok, "reason": opportunity_reason},
        "time": {"passed": time_ok, "reason": time_reason},
    }
    reasons = [r for r in (resource_reason, opportunity_reason, time_reason) if r is not None]
    decision = EXECUTE if (resources_ok and opportunity_ok and time_ok) else WAIT

    return ExecutionReadiness(task_id=task.id, decision=decision, reasons=reasons, checks=checks)
