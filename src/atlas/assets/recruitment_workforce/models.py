import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Self-contained: no atlas.core/atlas.brain imports, matching every other
# asset in the registry. new_id()/now() mirror atlas.brain.models' helpers
# but are local copies, not a shared dependency.


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# discovered -> qualified -> matched -> proposal_ready -> active -> won
#                                                              \-> lost (any time before won)
# proposal_ready -> active and active -> won only happen through the
# founder-approval gates (RecruitmentAgent.approve_outreach/approve_commitment)
# — external outreach and any agreement/placement/commitment are never
# automatic.
STAGES = ("discovered", "qualified", "matched", "proposal_ready", "active", "won", "lost")


@dataclass
class EmployerDemand:
    """Employer demand intake: one employer's stated workforce need."""

    industry: str
    employer_name: str
    role: str
    headcount: int
    rate_expectation_per_hour: float
    location: str = ""
    id: str = field(default_factory=lambda: new_id("demand"))
    created_at: str = field(default_factory=now)


@dataclass
class WorkforceSupplier:
    """Workforce supplier intake: an agency/pool that provides candidates."""

    name: str
    industry: str
    id: str = field(default_factory=lambda: new_id("supplier"))
    created_at: str = field(default_factory=now)


@dataclass
class CandidateRecord:
    """One candidate/worker in the pool, optionally linked to a supplier."""

    industry: str
    description: str
    pay_rate_expectation_per_hour: float
    supplier_id: str | None = None
    available: bool = True
    id: str = field(default_factory=lambda: new_id("candidate"))
    created_at: str = field(default_factory=now)


@dataclass
class Opportunity:
    """Tracks one employer-demand-to-workforce match from discovery to
    placement, including the revenue model and founder-approval flags."""

    industry: str
    employer_demand_id: str
    candidate_ids: list[str] = field(default_factory=list)
    stage: str = "discovered"
    fee_per_hour: float = 0.0
    placement_fee: float = 0.0
    recurring_monthly_revenue: float = 0.0
    estimated_gross_profit: float = 0.0
    outreach_approved: bool = False
    commitment_approved: bool = False
    # Set once, at creation, from the atlas.brain Task that caused this
    # opportunity to be created (RecruitmentAgent.run(task=...) — see
    # _create_missing_opportunities). None when no task drove creation
    # (direct CLI intake, or run() called with no task). Never rewritten by
    # later stage-advancement — an opportunity's attribution never moves.
    goal_id: str | None = None
    task_id: str | None = None
    id: str = field(default_factory=lambda: new_id("opp"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    history: list[dict] = field(default_factory=list)

    def transition(self, stage: str, reason: str = "") -> None:
        self.stage = stage
        self.updated_at = now()
        self.history.append({"at": self.updated_at, "stage": stage, "reason": reason})
