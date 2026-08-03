from dataclasses import asdict, dataclass, field

from atlas.brain.models import new_id, now


@dataclass
class Campaign:
    """The business unit ATLAS manages end-to-end (2026-08-03, architecture
    locked) — the Campaign Intelligence Layer's output, sitting between the
    Decision Engine and the Production Layer in the full pipeline:
    Research -> Evidence -> Decision Engine -> Campaign Intelligence ->
    Digital Influencer -> Production -> Publishing -> Measurement ->
    Finance -> Learning.

    A Campaign replaces an isolated product assignment as the real unit of
    work (see atlas.influencer.production, which generates every asset
    FROM a Campaign now, never from an isolated per-influencer
    assignment): it names the product/offer, which influencer(s) work it,
    the strategy across every dimension (platform/content/landing
    page/CTA), the plan (budget/timeline/success KPIs), and its own
    evidence-grounded confidence — recomputed over time via
    registry.refresh_confidence(), never permanently fixed (the same
    "nothing is permanently true" principle decide()/
    has_materially_changed() already apply to Decisions, applied here to a
    mutable, long-lived entity instead of an immutable, append-only one).

    `category` is not one of the founder's named fields but is structurally
    necessary: it's what ties a Campaign back to the same evidence taxonomy
    (Finding.category/CATEGORY_TASK_CATEGORIES) confidence_score() and the
    Decision Engine already use — the same justified, non-fabricated
    addition DigitalInfluencer.categories already was.

    `revenue_goal`/`budget`/`timeline` are stated targets/plans, not
    measured facts — the same class of transparent assumption
    ASSUMED_MONTHLY_LEADS already is; real measured performance stays in
    KPIRegistry/Ledger via `goal_id`, never duplicated here. `confidence_score`
    is real, computed data (from atlas.brain.confidence.confidence_score,
    reused unchanged — never a second, parallel scoring mechanism just for
    campaigns), snapshotted at creation/refresh time since a Campaign,
    unlike a Decision, is a mutable record that persists and gets updated
    rather than superseded by a new one each time evidence changes.
    """

    business_objective: str
    category: str = ""
    revenue_goal: float | None = None
    target_audience: str = ""
    customer_problem: str = ""
    product_offer: str = ""
    influencer_ids: list[str] = field(default_factory=list)
    platform_strategy: str = ""
    content_strategy: str = ""
    content_formats: list[str] = field(default_factory=list)
    landing_page_strategy: str = ""
    cta_strategy: str = ""
    budget: float | None = None
    timeline: dict = field(default_factory=dict)
    success_kpis: list[str] = field(default_factory=list)
    learning_history: list[dict] = field(default_factory=list)
    confidence_score: float | None = None
    goal_id: str | None = None  # the real Goal this campaign executes under, when one exists
    status: str = "proposed"  # proposed | active | paused | completed | cancelled
    id: str = field(default_factory=lambda: new_id("campaign"))
    created_at: str = field(default_factory=now)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Campaign":
        # Flat — unlike DigitalInfluencer, Campaign has no nested
        # dataclass fields, so Campaign(**data) reconstructs it directly.
        return Campaign(**data)
