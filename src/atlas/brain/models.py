import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Task/Proposal categories that always require human approval, regardless of
# the four risk axes below. "redesign_*" (any suffix) is handled separately
# in atlas.brain.risk via a prefix check, since it's an open family of
# categories rather than a fixed set.
ALWAYS_REQUIRES_APPROVAL = {"create_asset", "recruit_agent"}


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
    id: str = field(default_factory=lambda: new_id("goal"))
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

    def transition(self, status: str, reason: str = "") -> None:
        self.status = status
        self.updated_at = now()
        self.history.append({"at": self.updated_at, "status": status, "reason": reason})


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
    category is worth pursuing at all."""

    source: str
    category: str
    description: str
    evidence: str = ""
    provider: str = ""
    id: str = field(default_factory=lambda: new_id("finding"))
    created_at: str = field(default_factory=now)


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
    id: str = field(default_factory=lambda: new_id("proposal"))
    created_at: str = field(default_factory=now)
    resolved_at: str | None = None
