import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Self-contained: no atlas.core/atlas.brain imports, matching every other
# asset in the registry.


def new_id() -> str:
    return f"pub-{uuid.uuid4().hex[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


STATUSES = ("READY", "APPROVED", "QUEUED", "PUBLISHED", "FAILED", "CANCELLED")


@dataclass
class PublishPackage:
    """The one thing that ever crosses the Publishing Gateway boundary — a
    fully-built, verified package describing what *would* be published, if
    a real platform integration existed. This is a distinct entity from
    AffiliateOpportunity: the opportunity's lifecycle is about content
    approval, this one is about queue status. Two different concerns, not a
    duplicate state machine for the same thing (same distinction the
    Opportunity/Product/Campaign split in AFFILIATE_OPPORTUNITY_MODEL.md
    already established).
    """

    platform: str
    title: str
    description: str
    cta: str
    hashtags: list[str] = field(default_factory=list)
    affiliate_disclosure: str = ""
    media_references: list[str] = field(default_factory=list)  # placeholders only — nothing real
    # The founder's real affiliate tracking link, carried over from
    # AffiliateOpportunity.real_affiliate_link — "" for a placeholder-sourced
    # opportunity. This is what the founder actually copies into their real
    # bio/link tool before posting.
    tracking_link: str = ""
    status: str = "READY"
    opportunity_id: str | None = None
    goal_id: str | None = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    history: list[dict] = field(default_factory=list)

    def transition(self, status: str, reason: str = "") -> None:
        self.status = status
        self.updated_at = now()
        self.history.append({"at": self.updated_at, "status": status, "reason": reason})
