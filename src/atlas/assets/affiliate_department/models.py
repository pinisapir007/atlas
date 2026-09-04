import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from atlas.integrations.registry import get_provider

# Self-contained with respect to atlas.core/atlas.brain: no imports from
# either, matching every other asset in the registry. new_id()/now() are
# local copies of the same helpers atlas.brain.models and
# recruitment_workforce.models already use, not a shared dependency.
# atlas.integrations is a peer, dependency-free layer (like stdlib), not
# part of atlas.core/atlas.brain's orchestration — importing the real
# per-provider link validation from there instead of duplicating it here
# is exactly what that layer exists for.


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# discovered -> selected -> content_planned (then a brain-side founder-
# approval task is requested; see atlas.brain.affiliate_pipeline_advance).
# "lost" is reachable from "discovered" (rejected at evaluation). This is a
# deliberately reduced slice of the full Opportunity/Product/Campaign model
# in docs/AFFILIATE_OPPORTUNITY_MODEL.md — Qualified and Selected are
# collapsed into one evaluation pass here, and Published/Tracking/Completed
# are not implemented at all (no publishing, no external tracking).
#
# "researched" / "ranked" are used by the separate Affiliate Intelligence
# department (atlas.assets.affiliate_intelligence) — same model and store
# class, reused rather than duplicated, extended additively with two more
# stage values rather than a second, parallel state machine.
#
# "selected_for_marketing" / "content_packaged" / "approved_for_marketing"
# are used by Content Factory (atlas.assets.content_factory), continuing
# the same opportunity once the founder has chosen it in Affiliate
# Intelligence — again additive stage growth on the one shared model, not a
# new state machine.
#
# "editorial_passed" is used by Editorial Review (atlas.assets.editorial_review)
# — sits between content_packaged and the founder review request; founder
# review now triggers off editorial_passed, not raw content_packaged, so
# nothing reaches the founder before passing review.
STAGES = (
    "discovered",
    "researched",
    "ranked",
    "selected",
    "content_planned",
    "selected_for_marketing",
    "content_packaged",
    "editorial_passed",
    "approved_for_marketing",
    "lost",
)

def validate_provider_link(provider: str, real_affiliate_link: str) -> None:
    """Fail-closed intake guard. Raises ValueError — never silently accepts
    and never guesses a fix, same fail-closed philosophy as RiskPolicy/
    kpi_intake elsewhere in this codebase.

    Both "is this a supported provider" and "is this a valid link for that
    provider" are atlas.integrations's job — get_provider() already raises
    for an unrecognized name (checked against the real, live PROVIDERS
    registry), so there is deliberately no second, separately-maintained
    allowlist here that could fall out of sync with it. A previous version
    of this function had exactly that: a local SUPPORTED_PROVIDERS set that
    was supposed to mirror the registry but didn't actually derive from
    it — real single-source-of-truth debt, removed rather than patched.
    """
    if not get_provider(provider).validate_link(real_affiliate_link):
        raise ValueError(f"real_affiliate_link is not a valid {provider} link: {real_affiliate_link!r}")


def provider_tracking_link(
    provider: str,
    real_affiliate_link: str,
    campaign_key: str,
) -> str:
    """Return the real affiliate link with provider-supported attribution.

    Only modifies links for providers whose real tracking syntax ATLAS
    explicitly knows. Unknown/unimplemented providers remain byte-for-byte
    unchanged rather than guessing a tracking convention.
    """
    if not real_affiliate_link or not campaign_key:
        return real_affiliate_link

    if provider == "digistore24":
        from atlas.integrations.digistore24 import add_campaign_key

        return add_campaign_key(real_affiliate_link, campaign_key)

    return real_affiliate_link


@dataclass
class AffiliateOpportunity:
    """One affiliate opportunity moving through discovery, evaluation, and
    content planning. All estimation fields (estimated_conversion,
    competition, content_difficulty, commission_per_conversion) are
    placeholder/founder-judgment inputs, never measured data — there is no
    real affiliate program or tracking integration behind any of it."""

    product_name: str
    description: str
    category: str = "affiliate"
    commission_per_conversion: float = 0.0
    estimated_conversion: float = 0.0  # 0.0-1.0, placeholder
    competition: float = 0.0  # 0.0-1.0, placeholder, judgment-only
    content_difficulty: float = 0.0  # 0.0-1.0, placeholder, judgment-only
    notes: str = ""  # free-text research notes, set by ResearchAgent's enrichment pass
    score: float = 0.0  # set by the Affiliate Manager's evaluation pass, or RankingAgent's ranking pass
    # The founder's real, actual affiliate tracking link for a real, signed-up
    # program — "" for every placeholder/discovered-only opportunity. Set only
    # via AffiliateIntelligenceAgent.intake_real_product(); threaded through to
    # PublishPackage.tracking_link once a package is built.
    real_affiliate_link: str = ""
    # Which real affiliate network this came from (e.g. "digistore24") — ""
    # for placeholder/discovered-only opportunities. See
    # atlas.integrations.registry.PROVIDERS for what's actually supported.
    provider: str = ""
    # The network's own product identifier (e.g. Digistore24's numeric
    # product ID) — provider-specific, opaque to ATLAS, kept only for the
    # founder's own reference/reconciliation against that network's dashboard.
    provider_product_id: str = ""
    # The audience-facing marketing niche (e.g. "Keto Diet / Weight Loss") —
    # distinct from `category`, which is the provider's own product-type
    # classification (e.g. "software") used for platform bookkeeping only.
    # Content Factory's generator uses this for hooks/headlines/CTAs/content
    # ideas when set, falling back to `category` when it isn't (placeholder
    # opportunities never set this). Root-cause fix for generated copy that
    # read as generic "software" marketing for a niche product.
    marketing_niche: str = ""
    # The country/language this opportunity's real evidence points to —
    # set only by Opportunity Discovery V1 (atlas.brain.opportunity_
    # discovery_advance) from the most common real Finding.market behind
    # this opportunity's ranking (see atlas.brain.opportunity_ranking).
    # "" for every founder-manual intake and every opportunity with no
    # market-tagged evidence — never a guess.
    recommended_market: str = ""
    # {} until CreativeAgent runs; then {"type": "image"|"short_video",
    # "status": "brief_ready", "brief": {...}}. "status" only ever becomes
    # "ready" (with a "reference" key added) via
    # CreativeAgent.attach_real_asset() -- a founder recording a real asset
    # they produced outside ATLAS. No real image/video generation happens
    # inside ATLAS today; Publishing Gateway fail-closed refuses to build a
    # package until status == "ready".
    creative_assets: dict = field(default_factory=dict)
    stage: str = "discovered"
    content_brief: dict = field(default_factory=dict)
    # Content Factory's richer output (campaign summary, angles, hooks,
    # headlines, CTAs, platform suggestions, content ideas) — distinct from
    # content_brief, which is Affiliate Department's simpler Mission 003
    # artifact for a different pipeline.
    content_package: dict = field(default_factory=dict)
    content_review_rejections: int = 0
    # Editorial Review's own verdict/feedback/cycle-count — "" | "pass" |
    # "revision_required" | "reject". Cleared back to "" by Content Factory
    # after applying a fix, so the next evaluation is judged fresh.
    editorial_verdict: str = ""
    editorial_feedback: dict = field(default_factory=dict)
    editorial_cycles: int = 0
    # Set once, at creation, from the atlas.brain Task that caused this
    # opportunity to be created — never rewritten afterward, same rule as
    # recruitment_workforce.models.Opportunity.
    goal_id: str | None = None
    task_id: str | None = None
    id: str = field(default_factory=lambda: new_id("aopp"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    history: list[dict] = field(default_factory=list)

    def transition(self, stage: str, reason: str = "") -> None:
        self.stage = stage
        self.updated_at = now()
        self.history.append({"at": self.updated_at, "stage": stage, "reason": reason})
