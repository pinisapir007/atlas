from dataclasses import asdict, dataclass, field

from atlas.brain.models import new_id, now

# The Execution Orchestrator's step vocabulary (2026-08-03) — an explicit,
# documented, open-but-bounded set, the same discipline
# influencer.models.TEMPLATE_KINDS/confidence.CATEGORY_TASK_CATEGORIES
# already use. Deliberately narrow today, built only from real, already-
# existing capabilities:
#   verify_readiness       - pure check: every influencer_id resolves, at
#                             least one is assigned, campaign.goal_id is set
#   produce_content         - one per campaign.influencer_ids entry; calls
#                             the Content Production Layer directly
#                             (deterministic template assembly, no real
#                             generation)
#   request_founder_review  - dispatches one real Task (reversible=False),
#                             the ONE real "specialized agent" hand-off
#                             this orchestrator makes today — RiskPolicy/
#                             CEOBrain's existing tick() loop, not this
#                             module, decides and acts on it
#   check_measurement       - pure check: real profit() on campaign.goal_id;
#                             refreshes campaign confidence once measured
# Deliberately NOT wired to the existing affiliate_department/
# content_factory/editorial_review/creative_agent/publishing_gateway chain
# — that chain is opportunity-driven, not Campaign-driven, and bridging the
# two is a distinct, much larger increment, not attempted here (see
# CLAUDE.md).
STEP_KINDS = {"verify_readiness", "produce_content", "request_founder_review", "check_measurement"}

# pending: waiting on dependencies. ready: dependencies satisfied, not yet
# acted on (a transient state advance_execution() resolves within the same
# call — steps are never left "ready" between calls). dispatched: a real
# Task was created, waiting on its outcome. done/blocked/failed: terminal
# for this pass, but blocked is never permanent — the next advance_execution()
# call re-evaluates it fresh, the same "nothing is permanently true"
# resumability every other reopening mechanism in this codebase already has.
STEP_STATUSES = {"pending", "dispatched", "done", "blocked", "failed"}


@dataclass
class ExecutionStep:
    """One coordinated unit of a Campaign's execution — never the work
    itself. `kind` determines what advance_execution() does when this
    step's dependencies are satisfied: some kinds are pure, in-process
    checks (verify_readiness/check_measurement), one kind
    (produce_content) invokes the Content Production Layer directly (still
    not "specialized agent work" — it's ATLAS's own deterministic
    assembly, not a human department), and one kind
    (request_founder_review) creates a real Task and hands it to the
    existing Delegator/RiskPolicy/CEOBrain machinery — coordination, never
    execution, the founder's own framing.

    `depends_on` references other ExecutionStep ids within the same
    ExecutionPlan — the ordering/dependency graph. `task_id` correlates a
    dispatched step to the real Task it created, the same correlation-key
    pattern `source_opportunity_id`/`engine_id` already establish
    elsewhere. `result` is a structured, honest record of what actually
    happened (or why a step is blocked) — never a bare pass/fail flag with
    no explanation, the same full-traceability discipline `Decision.reasoning`
    already enforces.
    """

    campaign_id: str
    kind: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    influencer_id: str | None = None  # set for a per-influencer produce_content step
    task_id: str | None = None
    result: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("step"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)


@dataclass
class ExecutionPlan:
    """The Execution Orchestrator's real output: an ordered, dependency-
    aware set of ExecutionSteps for one Campaign — "an execution plan with
    ordered tasks and dependencies" (founder's framing). Steps are
    embedded (no independent lifecycle apart from their plan, the same
    reasoning Task.history/DigitalInfluencer's embedded lists already
    follow).

    `event_log` is the plan's audit trail — every status change
    advance_execution() makes is recorded here, never silently, the same
    provenance discipline Campaign.learning_history already established
    one layer up.

    "Event-driven" in this codebase means what it means everywhere else
    here: advance_execution() recomputes fresh from current real state
    every call (the same purity decide()/has_materially_changed() already
    rely on) rather than assuming stale progress — not a message-bus
    architecture, which does not exist anywhere in this codebase and isn't
    built here either. Resumability comes from that purity: call
    advance_execution() again (e.g. every CEOBrain.tick(), see
    orchestrator.advance_all_campaign_executions()) and any step that was
    blocked because its precondition wasn't met yet is re-evaluated fresh,
    with no special "retry" mechanism required.
    """

    campaign_id: str
    steps: list[ExecutionStep] = field(default_factory=list)
    status: str = "in_progress"  # in_progress | completed
    event_log: list[dict] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("plan"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "ExecutionPlan":
        # Nested ExecutionStep list needs explicit reconstruction — the
        # same wrinkle DigitalInfluencer.from_dict() already documents:
        # asdict() recurses out fine, Cls(**dict) does not reconstruct
        # dataclasses back in.
        data = dict(data)
        data["steps"] = [ExecutionStep(**s) for s in data["steps"]]
        return ExecutionPlan(**data)
