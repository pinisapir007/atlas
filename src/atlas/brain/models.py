import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from atlas.brain.time_service import TimeService, seconds_between


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Task/Proposal categories that always require human approval, regardless of
# the four risk axes below. "redesign_*" (any suffix) is handled separately
# in atlas.brain.risk via a prefix check, since it's an open family of
# categories rather than a fixed set.
#
# "affiliate_commercial_terms_needed" (Milestone 4, Business Plan Generator,
# 2026-08-13) is here purely to route through the existing structural
# Proposal/approve path (Delegator.is_structural() -> Delegator._propose()
# -> a real linked Proposal -> CEOBrain.approve() marks it applied and the
# Task "done") -- never to create an Asset. Without this, approve() (no
# linked Proposal would ever exist) falls through to Delegator.delegate()'s
# normal Registry category-matching, which -- since no real asset declares
# this category -- tries every other registered asset in turn until one
# doesn't raise UnsupportedVerb (the same failure class already found and
# fixed once before for campaign_execution), and task.status would never
# reach "done" either way. See docs/DESIGN_BUSINESS_PLAN_GENERATOR.md §4.
ALWAYS_REQUIRES_APPROVAL = {"create_asset", "recruit_agent", "affiliate_commercial_terms_needed"}


@dataclass
class Goal:
    """A durable business objective ATLAS plans and prioritizes work against."""

    description: str
    priority: int = 3  # 1 = highest
    status: str = "active"  # active | paused | done
    # "short" (cash-flow-now) or "long" (strategic-value-later) — lets the
    # Strategist rank goals within their own horizon instead of one bucket
    # where fast cash always outranks long-term asset-building.
    horizon: str = "short"
    # Founder's six-criteria estimate at goal creation, provisional by design:
    # expected_revenue, required_investment, time_to_first_profit (dollars/days),
    # scalability, automation_potential, long_term_strategic_value (0.0-1.0).
    # The Strategist blends this against measured KPI data over time rather
    # than treating it as a permanent fact.
    founder_estimate: dict = field(default_factory=dict)
    # Optional grouping tag when several Goals represent one revenue engine.
    engine_id: str | None = None
    # Canonical lifecycle state for SimplePlanner's generic fallback.
    # This is NOT a Task sentinel or manual reminder. When the exact
    # "Advance goal: <current description>" action completes successfully,
    # Monitor stores that fingerprint here. SimplePlanner will not replay
    # that identical fallback. If the Goal description later changes, the
    # fingerprint no longer matches; the new fallback may run and this field
    # is automatically overwritten when that new work completes.
    planner_completion_fingerprint: str = ""
    id: str = field(default_factory=lambda: new_id("goal"))
    created_at: str = field(default_factory=now)


@dataclass
class StrategicObjective:
    """The company's current strategic phase (2026-08-06, Strategic
    Objective V1) — the missing layer Strategist's scoring previously
    had no notion of. Before this existed, score_cash_flow/
    score_strategic_value were blended by a fixed rule tied only to a
    Goal's own `horizon` (short=100% cash flow, long=100% strategic
    value) — the same evidence produced the same decision regardless
    of what the company was actually trying to achieve right now.

    `cash_flow_weight`/`strategic_value_weight` (each 0.0-1.0, must
    sum to ~1.0 — validated at save time, never silently normalized)
    are the real, editable expression of a phase: an early "first
    $1,000, fastest, safest" objective weights cash flow heavily; a
    later "sustainable $10,000/month" objective weights scalability/
    automation/long-term value instead. `target_metric`/`target_value`
    are open, honest facts about the goal itself (e.g. "revenue",
    1000.0) — never enforced against a closed set, the same
    open-string discipline Finding.category/Task.category already
    establish.

    Never mutated or deleted once saved — setting a new objective is a
    new record, and the current one is simply the most recently
    created (see BrainMemory.current_strategic_objective), the same
    "recompute fresh from the latest real fact" discipline the
    Decision Engine already applies rather than a separately-tracked,
    driftable "current pointer" field.
    """

    description: str
    target_metric: str
    target_value: float
    cash_flow_weight: float
    strategic_value_weight: float
    id: str = field(default_factory=lambda: new_id("objective"))
    created_at: str = field(default_factory=now)


@dataclass
class Task:
    """One unit of work the brain plans, prioritizes, risk-gates, and delegates."""

    goal_id: str
    description: str
    category: str = "general"
    # Capability tag matched against Registry assets at delegation time
    # (e.g. "Triggerable"). None means the task can't be delegated to code.
    required_capability: str | None = "Triggerable"
    reversible: bool = False
    estimated_amount: float = 0.0
    involves_privileged_access: bool = False
    involves_legal_agreement: bool = False
    priority_score: float = 0.0
    status: str = "proposed"
    # proposed -> prioritized -> ready|pending_approval -> delegated ->
    # in_progress -> done|failed|blocked
    # pending_approval -> superseded is also terminal for work that became
    # obsolete because a newer Decision Engine verdict no longer supports
    # the proposal. It is neither failure nor owner rejection.
    assigned_asset_id: str | None = None
    # Set only by atlas.brain.pipeline_advance when this task exists purely
    # to continue a specific in-progress Recruitment opportunity. None for
    # every other task. This is the correlation key that prevents a duplicate
    # continuation task from being created while one is already open.
    source_opportunity_id: str | None = None
    id: str = field(default_factory=lambda: new_id("task"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    history: list[dict] = field(default_factory=list)
    # Time Awareness Engine V1 (2026-08-05) -- additive, real-execution
    # timing. started_at is set the first time this task's real work
    # actually begins: "delegated" is the real signal in this codebase
    # today (registry.dispatch() has already been called by the time
    # delegator.py transitions to it) -- "in_progress" is also honored
    # for forward compatibility with the lifecycle this class's own
    # docstring documents, even though no real code path reaches it yet.
    # finished_at/duration/execution_time are set once, on the first
    # real transition to "done" or "failed" -- "blocked" is deliberately
    # not terminal here, since a blocked task can still be picked up
    # later. duration is the real active-execution span (finished_at -
    # started_at); execution_time is the real total end-to-end span
    # (finished_at - created_at), including any time spent planned/
    # pending/approval-waiting before real dispatch began -- two
    # genuinely different real measurements, not a duplicate field.
    # updated_at (above) already IS "last_updated" -- no second,
    # redundantly-named field for the same real value.
    started_at: str | None = None
    finished_at: str | None = None
    duration: float | None = None
    execution_time: float | None = None
    # Intent -> Actual -> Verification (2026-08-17, ONE BRAIN Root
    # Implementation) -- additive, optional. `expected_outcome` is a
    # caller-declared, human-readable description of what "done" should
    # actually look like in the world -- never enforced/parsed
    # automatically, just recorded so a real, independent verification
    # step (case-specific code, the same class as
    # orchestrator.check_measurement/VerifiedClickAdvancer -- never a
    # generic VerificationEngine) has something to check against, and so
    # a future audit can see what was promised. "" (default) means this
    # Task carries no verification contract at all -- the exact, total
    # backward-compatible case every existing Task/caller already is.
    # `verification_status` is deliberately NOT folded into `status`
    # (execution progress) -- ACTUATOR SUCCESS != INTENT SUCCESS are two
    # separate facts, kept on two separate, orthogonal fields.
    # `verification_evidence_id` cites the real Finding/observation id
    # that proved it, the same evidence-citation discipline every other
    # real record in this codebase already uses (Opportunity.
    # evidence_finding_ids, Claim.evidence_finding_ids) -- never a bare
    # trust-me flag.
    expected_outcome: str = ""
    verification_status: str = "unknown"  # "unknown" | "verified_success" | "verified_failure"
    verification_evidence_id: str | None = None

    def transition(self, status: str, reason: str = "", time_service: "TimeService | None" = None) -> None:
        # The one, sole chokepoint for every Task status change (verified
        # by direct source inspection -- no other real code path mutates
        # `.status`). This is deliberately where the verification guard
        # lives: a Task that declared a real expected_outcome must never
        # reach "done" on the strength of an actuator's own self-report
        # alone -- "ACTUATOR REPORT is not source-of-truth for OUTCOME"
        # (locked ONE BRAIN principle). The guard only ever narrows an
        # existing caller's request (refuses "done"); it never changes
        # what "done" means for the vast majority of Tasks that declare
        # no expected_outcome at all -- those keep today's exact
        # behavior, unconditionally.
        if status == "done" and self.expected_outcome and self.verification_status != "verified_success":
            raise TaskVerificationRequired(
                f"Task {self.id} declares expected_outcome={self.expected_outcome!r} but "
                f"verification_status={self.verification_status!r} (requires 'verified_success') "
                "-- refusing to mark done without independent verification"
            )
        ts = time_service if time_service is not None else TimeService()
        self.status = status
        self.updated_at = now()
        self.history.append({"at": self.updated_at, "status": status, "reason": reason})

        if status in ("delegated", "in_progress") and self.started_at is None:
            self.started_at = ts.iso_timestamp()
        if status in ("done", "failed") and self.finished_at is None:
            self.finished_at = ts.iso_timestamp()
            if self.started_at is not None:
                self.duration = seconds_between(self.started_at, self.finished_at)
            self.execution_time = seconds_between(self.created_at, self.finished_at)

    def try_complete(self, reason: str, time_service: "TimeService | None" = None) -> bool:
        """The one, shared, safe way every "done"-setting caller (Monitor,
        CEOBrain.approve) should mark a Task complete, instead of calling
        transition("done", ...) directly. Attempts "done"; if the
        verification guard above refuses it, falls back to "blocked" (an
        existing, legitimate, resumable status -- never a fabricated
        "partial" value) with the guard's own reason appended, so the
        Task is visibly held pending real verification rather than
        silently stuck or falsely completed. Returns whether it actually
        completed."""
        try:
            self.transition("done", reason, time_service)
            return True
        except TaskVerificationRequired as guard_error:
            self.transition("blocked", f"{reason} -- {guard_error}", time_service)
            return False


class TaskVerificationRequired(ValueError):
    """Raised by Task.transition("done", ...) when expected_outcome is
    declared but verification_status has not independently confirmed
    verified_success -- the enforcement point for "actuator success !=
    intent success". Callers that don't want this to propagate should
    use Task.try_complete() instead of calling transition("done", ...)
    directly."""


@dataclass
class Finding:
    """One durable record of something ATLAS's Intelligence layer learned
    exists in the world — a candidate opportunity, market signal, or
    business-model pattern — kept regardless of whether it ever becomes a
    Task. category is an open string (affiliate, digital_product, youtube,
    ugc, recruitment, content, ...), the same convention Task.category
    already uses, so a channel that has no dispatchable asset yet is still
    recorded honestly rather than dropped. evidence is a real URL/citation
    when one exists and "" otherwise — never a fabricated source.

    provider is optional and orthogonal to category: "" for a finding about
    a channel generally (e.g. "AI-tool affiliate programs pay 20-50%
    recurring"), or a specific registered provider name (e.g.
    "digistore24") when the finding is evidence about *that platform*
    specifically (e.g. "Digistore24 has X real commission structure"),
    scoped one level deeper than category — this is what makes it possible
    to rank *which platform* within a category, not just whether the
    category is worth pursuing at all.

    subject and market (added 2026-08-03, Opportunity Discovery V1) are two
    more optional, orthogonal scoping dimensions, the same shape as
    provider: subject names the specific candidate product/topic this
    evidence is about ("" for a category-general finding) — what makes it
    possible to rank *which specific opportunity* within a category, one
    level deeper than provider (see atlas.brain.opportunity_ranking).
    market names the country/language this evidence applies to when known
    ("" when general) — feeds the recommended-market signal on a ranked
    opportunity. Neither is inferred; both are "" unless the source of the
    finding actually states them."""

    source: str
    category: str
    description: str
    evidence: str = ""
    provider: str = ""
    subject: str = ""
    market: str = ""
    # claimant (2026-08-17, ONE BRAIN Evidence Provenance) -- WHO in the
    # real world is making this assertion (a vendor, a named reviewer, a
    # company) -- deliberately distinct from `source` (which ATLAS
    # sensor/component observed it) and from `provider` (which external
    # PLATFORM the evidence came through). Never guessed/inferred from a
    # domain or from `source` -- only ever set by the same brain-layer
    # grounding code that already decides `subject`/`category`, and only
    # when genuinely known from the real observation. "" (the default,
    # and the honest value whenever the real claimant isn't knowable --
    # e.g. a page merely relaying another party's statement with no
    # explicit byline/attribution) means UNKNOWN, never a fabricated
    # guess -- see atlas.brain.evidence_provenance for how this
    # participates in independent-source counting.
    claimant: str = ""
    # evidence_role (2026-08-17, ONE BRAIN Evidence Role Gate) -- WHAT KIND
    # of relationship this evidence artifact has to its real-world source,
    # orthogonal to WHO (claimant) and WHERE (evidence/origin). Open string,
    # documented, non-exhaustive vocabulary (never a closed enum, the same
    # convention Finding.category/Claim.claim_type already use):
    #   "primary_observation" -- no external claimant exists at all (ATLAS
    #       directly observing a scene/screen; a real-world property, not
    #       an assertion).
    #   "direct_assertion" -- the artifact IS its real claimant's own,
    #       first-party statement, hosted on that claimant's own origin
    #       (a vendor's own page, a platform reporting on itself).
    #   "relay_or_quote" -- the artifact repeats/quotes a claimant who is
    #       NOT the artifact's own origin (an article quoting a vendor, a
    #       syndicated copy) -- the real danger case for false
    #       independence: many different origins can relay the same one
    #       real underlying claimant.
    #   "aggregated_report" -- the artifact bundles multiple real,
    #       possibly-different-claimant propositions into one observed
    #       record (e.g. a Marketplace listing mixing vendor-set fields
    #       with platform-computed statistics) -- deliberately never
    #       split into multiple Findings (see evidence_provenance.py).
    #   "" -- UNKNOWN, the honest default whenever the role isn't
    #       structurally provable from the writer's own real, structured
    #       input -- never guessed from a URL/domain/sensor name.
    # Only ever set by the same brain-layer grounding code that already
    # decides claimant/subject/category, and only when the writer's own
    # structure proves it (see evidence_provenance.py for exactly how
    # this gates independent-source counting).
    evidence_role: str = ""
    # Stage 7 Observation Standard: when this evidence was actually
    # observed, distinct from created_at (when the durable record was
    # created). Empty means genuinely unknown for legacy/manual records.
    observed_at: str = ""
    # Precise position inside a larger source when known: page/section,
    # paragraph, timestamp/range, frame, etc. Empty means source-level
    # evidence only -- never a fabricated locator.
    evidence_locator: str = ""
    # Exact source excerpt that directly supports this Finding when one
    # was actually verified. Empty means no exact excerpt was available
    # or provable -- never a reconstructed/paraphrased quote.
    evidence_excerpt: str = ""
    # Stable fingerprint of the real observed source content. Enables
    # later longitudinal change detection without treating a URL alone
    # as proof that its contents stayed the same.
    content_hash: str = ""
    id: str = field(default_factory=lambda: new_id("finding"))
    created_at: str = field(default_factory=now)


@dataclass
class SuccessLaw:
    """A generalized, reusable business principle ATLAS has extracted
    from real external evidence — never a literal implementation to
    copy. Founder's explicit standing rule (2026-08-03): "Every external
    source (video, article, course, creator, company, or successful
    business) should be treated as intelligence, never as a blueprint...
    ATLAS never copies implementations. ATLAS extracts reusable business
    intelligence."

    This is the real, buildable half of that directive: a durable,
    evidence-linked place to RECORD a Success Law once one is identified,
    so it becomes traceable business intelligence instead of living only
    in a conversation. It is deliberately NOT an automated extraction
    tool — no real content-analysis/LLM integration exists anywhere in
    this codebase to read a video/article and derive a principle from it
    on its own; that would be its own separate, explicit, credentialed
    decision, the same class this codebase has deferred everywhere else
    (ContentPublisher, MarketSignalProvider). Today a SuccessLaw is
    recorded by the founder (or, once one exists, a future real analysis
    tool) — this module just makes sure it's captured honestly and stays
    traceable to real evidence.

    `principle` must always be phrased as a transferable rule (e.g.
    "first-person testimonial framing outperforms feature-listing for
    consumer health products"), never as "do what {source} did" — the
    structural separation from `source_description` (what was actually
    observed) is what keeps a Success Law from silently becoming a
    blueprint to copy. `evidence_finding_ids` cites real Findings (each
    already carrying its own real `evidence` URL) this principle is
    actually grounded in — a law with none is an untested hypothesis, not
    a validated one; check `bool(law.evidence_finding_ids)` at any call
    site that needs to distinguish the two, rather than trusting a
    separately-stored status field that could drift out of sync.
    `applicable_business_models` is the founder's own explicit
    generalization test ("how can these principles be generalized across
    all business models") — an open list of categories, the same
    convention as `Finding.category`, not fixed to whichever single
    business ATLAS happened to observe it in."""

    principle: str
    source_description: str
    evidence_finding_ids: list[str] = field(default_factory=list)
    applicable_business_models: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("law"))
    created_at: str = field(default_factory=now)


# Valid FutureItem field values -- explicit, documented sets (the same
# "explicit, documented set" discipline confidence.CATEGORY_TASK_CATEGORIES
# already established), not open strings, since these three fields drive
# real lifecycle/enforcement logic in atlas.brain.future_items rather than
# being descriptive metadata like Finding.category.
FUTURE_ITEM_TYPES = {"candidate", "gate"}
FUTURE_ITEM_STATUSES = {"open", "triggered", "resolved"}
FUTURE_ITEM_RESOLUTIONS = {"implement", "reject", "deferred_again", "already_satisfied"}


@dataclass
class FutureItem:
    """Future Capability Recall + Gates (2026-08-15, Phase 1): a durable,
    evidence-linked record of something ATLAS/the founder deliberately
    deferred to a later, real, checkable moment -- built specifically so
    a deferred decision cannot become a passive note buried in a
    document that everyone quietly forgets to revisit. Lives in
    KnowledgeBase, the same store SuccessLaw already established for
    "durable, evidence-linked, non-committing Intelligence-layer record"
    -- this is one synthesis level further: a SuccessLaw is an extracted
    principle; a FutureItem is a deferred decision *about* one or more
    principles/capabilities.

    Two distinct kinds, `type`: a "candidate" is a real, useful idea that
    should be re-evaluated when its trigger fires but never blocks
    anything on its own. A "gate" is stronger -- founder/architecture
    declared it must be explicitly resolved before some real progression
    continues (see atlas.brain.future_items for what "resolved before
    progression" can and cannot mean today, since Roadmap milestones are
    not yet a coded, checkable state -- a real, named architectural
    limit, not silently pretended away).

    `trigger_check` is a real, registered key into
    atlas.brain.future_items.TRIGGER_CHECKS -- a deterministic, testable
    predicate over real system state -- never free text like "when we
    reach M6", which is exactly the un-enforceable "someone will
    remember" pattern this whole mechanism exists to replace.
    `atlas.brain.future_items.UNWIRED_TRIGGER_CHECK` is the one other
    valid value: an explicit, honest "no real predicate exists yet" --
    preferred over inventing a fake one just to look wired up.

    `status` (open -> triggered -> resolved) and `resolution` are
    deliberately two separate fields, the same split Proposal.status
    (lifecycle) and Decision.verdict (the actual verdict) already keep
    separate elsewhere in this codebase -- resolving *how* is a
    different fact from *whether* it's been resolved yet.
    `resolution_notes` records the real reasoning; `next_trigger_check`
    is set only when `resolution == "deferred_again"`, naming what this
    item becomes (see resolve_future_item()). `superseded_by_id` chains
    to the new FutureItem a "deferred_again" resolution creates -- the
    same superseded_id chain Decision already uses, so the full history
    of how a deferred idea moved through re-evaluations stays on record,
    never overwritten.

    Never silently marked "seen"/"acknowledged" -- there is deliberately
    no such field. The only way a due item stops being surfaced is a
    real, explicit resolution being recorded; recomputing due-ness fresh
    every time (see atlas.brain.future_items.due_future_items()) rather
    than storing a one-shot "notified" flag is what makes forgetting it
    structurally impossible, not just discouraged."""

    type: str  # "candidate" | "gate" -- see FUTURE_ITEM_TYPES
    title: str
    rationale: str
    trigger_description: str  # human-readable explanation of what the trigger means
    trigger_check: str  # a real key in TRIGGER_CHECKS, or UNWIRED_TRIGGER_CHECK
    source_description: str = ""  # what real-world source this was identified from, mirrors SuccessLaw's split
    evidence_finding_ids: list[str] = field(default_factory=list)
    applicable_capabilities: list[str] = field(default_factory=list)  # open list of capability tags this item is about
    status: str = "open"  # "open" | "triggered" | "resolved" -- see FUTURE_ITEM_STATUSES
    resolution: str | None = None  # see FUTURE_ITEM_RESOLUTIONS, set only once status == "resolved"
    resolution_notes: str = ""
    next_trigger_check: str | None = None  # set only when resolution == "deferred_again"
    superseded_by_id: str | None = None  # the new FutureItem a "deferred_again" resolution created, if any
    id: str = field(default_factory=lambda: new_id("future"))
    created_at: str = field(default_factory=now)
    triggered_at: str | None = None
    resolved_at: str | None = None


@dataclass
class Decision:
    """One Decision Engine verdict on a category, with full provenance.

    The Decision Engine is the only component allowed to produce these —
    the Intelligence Layer (Finding/KnowledgeBase/confidence_score) never
    decides, only discovers and measures (standing architecture, locked
    2026-08-02). Every field here is either a citation (evidence_finding_ids,
    factors) or a structured fact (context) — reasoning is a deterministic
    string built from those fields, never freeform generated text, so
    "why" is always traceable to what's actually stored, not a plausible-
    sounding explanation that may not reflect the real computation.

    Decisions are never overwritten — a changed verdict for the same
    category is a new Decision record (superseded_id points at the one it
    replaces), so the full history of how ATLAS's judgment moved as
    evidence changed is preserved, never lost.
    """

    category: str
    verdict: str  # "invest" | "already_invested" | "already_proposed" | "insufficient_evidence" | "propose_capability"
    confidence: float | None  # from confidence_score() — the Intelligence input, unmodified
    factors: dict  # confidence_score()'s per-factor breakdown, cited as-is
    evidence_finding_ids: list[str] = field(default_factory=list)
    # Company-context inputs actually available today — deliberately not a
    # fabricated resource/budget model. See decision_engine.py for what's
    # honestly known vs. not.
    context: dict = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    reasoning: str = ""
    goal_id: str | None = None  # set only when verdict == "invest" or "propose_capability" and a Goal was created
    superseded_id: str | None = None  # the prior Decision for this category this one reopens/replaces, if any
    # Which registered CommerceProvider ATLAS would use for this category,
    # per rank_providers() — set only on an "invest" verdict with at least
    # one eligible provider. None either because the verdict isn't "invest",
    # or because no provider is registered for this category yet (a
    # capability gap, not a ranking failure). provider_ranking (in context)
    # carries the full comparison, not just the winner — so a Decision
    # shows what else was considered, not only what was chosen.
    chosen_provider: str | None = None
    id: str = field(default_factory=lambda: new_id("decision"))
    created_at: str = field(default_factory=now)


@dataclass
class LedgerEntry:
    """One immutable record of a real financial event, spanning the full
    lifecycle a business transaction moves through: revenue is claimed, cash
    is settled, a fee is deducted, a refund reverses some or all of it.
    Never mutated — a correction is a new entry (kind="refund"), never an
    edit to a past one, the same append-only discipline DecisionLog already
    uses for Decisions.

    Purely additive to KPIRegistry's revenue_<goal_id>/cost_<goal_id>/
    settled_<goal_id> aggregates: recording a LedgerEntry never replaces the
    accumulate-onto-the-running-total behavior kpi_intake.py already has —
    cashflow.py/confidence.py keep reading those series unchanged. This is
    the detail/audit layer underneath that aggregate, not a second decision
    mechanism.

    Deliberately generic across every current and future platform
    (Digistore24, Amazon, YouTube, TikTok, Shopify, Etsy, PayPal, Wise,
    Stripe, a bank account, or "" for a founder-attested/manual event) via
    `provider` — orthogonal to `kind`, the same relationship Finding.provider
    already has to Finding.category. A new platform never needs a new
    LedgerEntry field or a new kind.
    """

    goal_id: str
    kind: str  # "revenue_claimed" | "cash_settled" | "cost" | "fee" | "refund"
    amount: float
    # Correlates every entry belonging to the same real-world transaction
    # across its lifecycle (claim -> settlement -> fee -> refund) when one
    # real ID is actually known (e.g. a future provider's own order/payout
    # ID). "" for founder-reported entries today — a payout is often a
    # batch across multiple sales, so inventing a one-to-one link here
    # would be a fabricated correlation, not a real one.
    transaction_id: str = ""
    provider: str = ""  # which platform/account this event came from
    provider_event_id: str = ""
    currency: str = ""
    category: str = ""  # sub-classification for cost/fee entries, e.g. "commission", "ad_spend", "platform_fee"
    evidence: str = ""  # what proves this happened — never fabricated, "" when unverified
    document_ref: str = ""  # pointer to a stored invoice/receipt/statement, when one exists
    id: str = field(default_factory=lambda: new_id("ledger"))
    created_at: str = field(default_factory=now)


@dataclass
class Proposal:
    """A structural decision ATLAS wants to make but cannot execute itself:
    creating an asset, recruiting an agent, or redesigning part of the
    business. Always starts pending_approval; a human resolves it."""

    task_id: str
    kind: str  # "create_asset" | "recruit_agent" | "redesign"
    rationale: str
    evidence: list[str] = field(default_factory=list)
    baseline_metrics: dict = field(default_factory=dict)
    status: str = "pending_approval"
    # pending_approval -> approved -> applied -> confirmed|needs_review | rejected
    # pending_approval -> superseded when a newer Decision Engine verdict
    # makes the structural proposal obsolete before the owner acts on it.
    id: str = field(default_factory=lambda: new_id("proposal"))
    created_at: str = field(default_factory=now)
    resolved_at: str | None = None


# Minimal lifecycle stages shared by every real channel -- deliberately NOT
# the 10-value atlas.assets.affiliate_department.models.STAGES enum, whose
# later values (content_planned, selected_for_marketing, content_packaged,
# editorial_passed, approved_for_marketing) are the affiliate content-
# production pipeline's OWN downstream stages, not part of what "having an
# opportunity" universally means (docs/DESIGN_OPPORTUNITY_UNIVERSAL_CORE.md).
# Everything past "selected" is a channel-specific extension's concern, not
# this entity's.
OPPORTUNITY_STAGES = ("discovered", "researched", "ranked", "selected", "lost")


@dataclass
class Opportunity:
    """Opportunity Universal Core (2026-08-11, docs/
    DESIGN_OPPORTUNITY_UNIVERSAL_CORE.md) -- the real Domain entity named
    in the Specification's own 16-entity list from the start, but never
    given a general, channel-agnostic implementation until now. The one
    place a specific business candidate exists with its own identity,
    after real evidence (Finding) exists about it but before any real
    commitment (Goal) has been made -- the gap Qualification Run #2
    surfaced: Executive Reasoning has real Decisions to compare, but
    nothing durable and channel-agnostic for those Decisions' own
    candidates to have first accumulated evidence around.

    Every field here was individually tested against
    atlas.assets.affiliate_department.models.AffiliateOpportunity,
    field by field, and kept only if the underlying business concept
    (not the field's specific shape) would be needed by ANY real channel
    (affiliate, saas, content, marketplace, ...), not just affiliate.
    `commission_per_conversion`, `real_affiliate_link`,
    `provider_product_id`, the whole content_brief/content_package/
    editorial_* cluster, `estimated_conversion`, `content_difficulty`, and
    every STAGES value past "selected" were deliberately tested and
    excluded -- they are real, but they belong to the affiliate channel's
    own downstream extension, never to this core. A future channel-
    specific extension is expected to ADD fields on top of this core, the
    same relationship AffiliateOpportunity is expected to eventually have
    to it -- this class is never itself extended with channel-specific
    fields.

    Does not replace AffiliateOpportunity, Decision, or Goal -- it is the
    real, previously-missing stage between them (Finding -> Opportunity ->
    Reasoning -> Decision -> Goal), not a substitute for any of them.
    """

    subject: str  # the specific real candidate this is about -- same concept as Finding.subject, given its own durable identity here
    description: str
    category: str = ""
    marketing_niche: str = ""  # the real target audience/niche, distinct from `category`'s structural classification
    recommended_market: str = ""  # same concept and convention as Finding.market -- "" unless real evidence actually states it
    competition: float | None = None  # 0.0-1.0 real competitive-intensity assessment; None means not yet assessed, never a fabricated default
    score: float | None = None  # a real evaluation number; the FORMULA that produces it is a channel's own concern, not this core's
    provider: str = ""  # a real external platform/network this operates through, when one exists -- "" otherwise, never guessed
    creative_assets: list[str] = field(default_factory=list)  # real file paths/URLs only, never a fabricated placeholder
    evidence_finding_ids: list[str] = field(default_factory=list)  # real Finding ids this opportunity has genuinely accumulated evidence from
    stage: str = "discovered"  # one of OPPORTUNITY_STAGES
    # Set once, at creation or at commitment -- never rewritten afterward,
    # the same rule every other correlation field in this codebase
    # (Task.source_opportunity_id, AffiliateOpportunity.goal_id) follows.
    goal_id: str | None = None
    task_id: str | None = None
    id: str = field(default_factory=lambda: new_id("opportunity"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    history: list[dict] = field(default_factory=list)

    def transition(self, stage: str, reason: str = "") -> None:
        self.stage = stage
        self.updated_at = now()
        self.history.append({"at": self.updated_at, "stage": stage, "reason": reason})


@dataclass
class Claim:
    """Cognitive Foundation (2026-08-15, Design Lock approved) — the real,
    minimal seam that closes the "new kind of relationship/hypothesis
    always requires a new field/dataclass" ceiling found by architecture
    review: ATLAS can represent a genuinely novel relation, attribute, or
    hypothesis about anything the moment one is formed (by a human, or by
    atlas.brain.reasoning_claims.reason(), the general LLM-backed
    reasoning call), without any code change — `predicate` is an open
    string, the same convention Finding.category already established,
    never a closed enum.

    A Claim is knowledge/reasoning state — NOT a Fact, NOT Evidence, NOT
    a Conclusion, and NOT Permission. It never gates a commercial,
    publishing, or spending action by itself (see the structural firewall
    in atlas.brain.reasoning_claims — that module never imports
    Delegator/Registry/RiskPolicy); any real action motivated by a Claim
    still goes through a real Task/Proposal, unchanged.

    `subject_id`/`object_id` reference any existing entity's real id
    (Finding, Opportunity, AffiliateOpportunity, another Claim, ...) —
    this dataclass deliberately never enforces which kind, the same
    "bare id pointer" convention every other cross-record reference in
    this codebase already uses. `object_id` is set only when the claim
    relates `subject_id` to another specific entity (e.g.
    predicate="possibly_same_as"); `object_value` is set instead when the
    claim asserts a literal attribute/value about `subject_id` alone
    (e.g. predicate="has_attribute", object_value="protein_source=whey").
    Setting both is rejected at save time — a claim cannot answer "what
    does this relate to" two different ways at once. Setting neither is
    valid: a unary claim about `subject_id` alone (e.g.
    predicate="needs_investigation").

    `evidence_finding_ids` MUST resolve to real Finding ids, enforced at
    save time — never a Claim id. This is the structural self-
    contamination firewall: an LLM-produced Claim's own assertion can
    never become evidence for itself or for any other Claim, because the
    schema itself makes the two lists (`evidence_finding_ids` vs.
    `prior_claim_ids`, below) impossible to conflate. Confidence is
    deliberately NOT a stored field — see
    atlas.brain.claims.claim_confidence(), computed fresh, exclusively
    from THIS claim's own `evidence_finding_ids` (never a broader
    category/subject scan the way confidence.source_corroboration_score()
    legitimately does for category-level confidence — a Claim may only
    gain epistemic support from evidence explicitly linked to it). An
    honest Finding-count approximation, not a verified independent-
    source check — the same known limitation
    confidence.source_corroboration_score()'s own docstring already
    states, inherited here rather than silently promised away.

    `contradicted_by_finding_ids` is a separate list, never folded into
    `evidence_finding_ids` with a negative sign — supporting and
    contradicting evidence are never combined into one naive number (no
    "3 supports minus 1 contradiction = still 75% true" arithmetic
    anywhere in this codebase). See atlas.brain.claims.claim_status() for
    how the two lists combine into an honest state
    (supported/contradicted/ambiguous/insufficient_evidence/superseded) —
    derived fresh from real fields, never a separately-stored status that
    could drift out of sync, the same "currentness computed, not stored"
    discipline SuccessLaw's own bool(evidence_finding_ids) check already
    established.

    `prior_claim_ids` are Claims fed as CONTEXT to a reasoning call
    (see reason()) — explicitly distinct from `evidence_finding_ids`
    because a prior Claim is a lead to re-validate, never proof. A Claim
    with no evidence at all (an unresolved, still-open hypothesis) is a
    legitimate, permanent state — "insufficient_evidence" is not
    "forgotten"; ATLAS must be able to remember a coherent hypothesis it
    cannot yet confirm, or it can never return to investigate it.

    `question` records the literal question that led to this Claim when
    `source == "reason_llm"` ("" for a manually-created Claim) — the one
    piece of reasoning provenance `predicate`/`object_id`/`object_value`
    alone don't capture (they record WHAT was concluded, not what was
    asked). Deliberately not a raw chain-of-thought transcript — a
    concise, structured provenance field, the same class of "enough to
    audit, not a fabricated appearance of transparency" already
    established elsewhere in this codebase.

    `superseded_by_id` is set on the OLD Claim, pointing FORWARD at its
    replacement — the same direction FutureItem.superseded_by_id already
    uses (not Decision.superseded_id's backward direction), specifically
    because "which Claim superseded this one" must be answerable by
    reading the old record itself, not by searching every other Claim for
    a backward pointer. Set once, at the moment of revision (mirrors
    future_items.resolve_future_item()'s single mutate-and-resave) — the
    old Claim's own content is never rewritten, only this one pointer.

    `claim_type` (2026-08-16, Semantic Grounding Wiring) — a SECOND,
    deliberately ORTHOGONAL axis to `claim_status()`. `claim_status()`
    answers "what is this claim's evidence situation right now"
    (supported/contradicted/ambiguous/insufficient_evidence/superseded).
    `claim_type` answers a completely different question: "what KIND of
    assertion is this" — e.g. "Digistore24 shows 60% commission" (a
    near-direct observation, evidence-quoted) versus "60% commission
    makes this product attractive" (a business inference/hypothesis) can
    both be `claim_status() == "supported"` while being epistemically
    very different claims. Confusing the two axes into one would let a
    speculative inference "borrow" the apparent certainty of a directly-
    observed fact merely because both happen to have real evidence
    attached — exactly what this field exists to keep separate. Open
    string (same convention as `predicate`/`Finding.category` — no closed
    enum, never enforced at save time), with a small, DOCUMENTED,
    non-exhaustive vocabulary: "observation" (near-direct restatement of
    what a source itself states), "inference" (a conclusion drawn FROM
    evidence, not directly stated by it), "assumption" (accepted as a
    working premise, not itself evidenced), "hypothesis" (a candidate
    explanation still to be tested), "validated_conclusion" (an inference
    that has since been checked against real outcomes). Set by the
    CREATOR at Claim-creation time (the same way `source` already is) —
    never derived/guessed after the fact, because only the creator (a
    human, or the specific `reason()` call forming it) actually knows
    which kind of assertion is being made; deriving it heuristically from
    `predicate` text or `source` would be exactly the kind of guessing
    this codebase's fail-closed discipline forbids elsewhere. Defaults to
    `""` (not yet classified) — the same honest-absence convention as
    `Finding.evidence`'s own `""` default, never a fabricated guess."""

    subject_id: str
    predicate: str
    object_id: str | None = None
    object_value: str | None = None
    evidence_finding_ids: list[str] = field(default_factory=list)
    contradicted_by_finding_ids: list[str] = field(default_factory=list)
    prior_claim_ids: list[str] = field(default_factory=list)
    question: str = ""
    source: str = "manual"  # "manual" | "reason_llm"
    claim_type: str = ""  # "" | "observation" | "inference" | "assumption" | "hypothesis" | "validated_conclusion"
    superseded_by_id: str | None = None
    id: str = field(default_factory=lambda: new_id("claim"))
    created_at: str = field(default_factory=now)


INVESTIGATION_STATUSES = ("open", "waiting_for_evidence", "ready_for_evaluation", "rejected", "closed")


@dataclass
class Investigation:
    """The real, minimal pre-Opportunity WORKFLOW-state owner (2026-08-17,
    ONE BRAIN Root Implementation) -- proven genuinely missing across
    three separate audit rounds, after Claim (epistemic: "what is known"),
    Goal (locked as the decisive business commitment itself, no subject
    field, cannot represent "just looking into this"), Task (requires a
    real goal_id -- structurally cannot exist before a Goal), and
    Proposal (requires a real task_id, one layer further into the same
    chicken-and-egg problem) were each checked and rejected in turn.

    Deliberately NOT built on Claim: a Claim asserts a fact about the
    world (an epistemic proposition, with its own evidence/contradiction/
    confidence machinery via claim_status()/claim_confidence()) --
    "we decided to keep investigating this" is a WORKFLOW decision, a
    genuinely different kind of statement, and forcing it into Claim would
    repeat the exact class of mistake this codebase already corrected
    once (Claim being asked to double as workflow state).

    Represents "I saw something that might be interesting enough to
    investigate, I remember why, but I don't have enough evidence yet to
    call it an Opportunity" -- sense-agnostic (Marketplace/Research/any
    future sense feeds it identically), never itself a creator of
    Opportunity/Goal/Task -- see atlas.brain.investigation_advance for the
    one, thin bridge that connects it to real evidence-collection, and
    atlas.brain.opportunity_advance (Bridge 1) for the only place an
    Investigation's evidence can ever actually become a real Opportunity.

    `subject_id` is the (possibly still-local, not-yet-canonicalized)
    subject a sense first observed -- the same identity a Finding/Claim
    about the same real-world thing would carry. `status` is a small,
    closed, deliberately non-expanded vocabulary
    (INVESTIGATION_STATUSES) -- open (just started) -> waiting_for_evidence
    (missing_evidence identified, request made) -> ready_for_evaluation
    (evidence returned, ready for Bridge 1 to judge) -> closed (Bridge 1
    created a real Opportunity for this subject -- the Investigation is
    never deleted, kept as the durable "how we got here" record) or
    rejected (evidence turned out not to support it). `missing_evidence`
    is a plain, human-readable description of what's still needed --
    never a structured query object, matching the same "editable,
    honest, not fabricated-precision" discipline every other free-text
    reason field in this codebase already uses."""

    subject_id: str
    category: str
    status: str = "open"
    reason_opened: str = ""
    supporting_claim_ids: list[str] = field(default_factory=list)
    supporting_finding_ids: list[str] = field(default_factory=list)
    contradicting_claim_ids: list[str] = field(default_factory=list)
    missing_evidence: str = ""
    closed_reason: str = ""
    id: str = field(default_factory=lambda: new_id("investigation"))
    opened_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
