import hashlib
from dataclasses import dataclass, field

from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunity_ranking import cited_evidence
from atlas.brand.models import Brand
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry, link_brand

# The Brand Factory (2026-08-03) -- the next step in the founder's stated
# end-to-end loop, immediately after Digital Influencer creation: "create
# the digital influencer/persona if needed -> create the brand -> create
# the Shopify store...". Same split as influencer.factory: BrandDraft
# carries only real, evidence-derived/structural facts (niche/category/
# market/recommended_name -- the last defaulting to the real product name,
# not an invented one, since many real digital businesses use the product
# name as the brand name). tagline/visual_identity/voice have no real
# evidence source anywhere in this codebase and live on BrandSuggestion
# instead (suggest_brand()) -- the founder's explicit "AI-suggested,
# clearly labeled, deterministic, always editable" treatment, the same one
# established for a Digital Influencer's WHO fields, applied consistently
# here rather than re-litigated.

# Marks every Task this factory creates so create_brand_from_proposal()
# can tell a real Brand proposal apart from a Digital Influencer Factory
# proposal -- both share Task.category == "create_asset" and can share the
# same source_opportunity_id (one opportunity can justify both a brand and
# an influencer), so category + source_opportunity_id alone isn't enough
# to distinguish which factory a given task belongs to.
TASK_MARKER = "Brand Factory:"


@dataclass
class BrandDraft:
    """Real, evidence-derived facts justifying a new Brand -- mirrors
    influencer.factory.InfluencerDraft's shape and discipline exactly.
    Purely computed on demand by draft_brand_proposal(), never persisted
    on its own, for the same reason InfluencerDraft isn't: a stored draft
    would silently go stale the moment new evidence arrives."""

    recommended_name: str
    recommended_niche: str
    recommended_category: str
    recommended_market: str
    source_opportunity_id: str
    rationale: str
    evidence: list[str] = field(default_factory=list)


def draft_brand_proposal(opportunity: AffiliateOpportunity, knowledge: KnowledgeBase) -> BrandDraft:
    """Builds the real recommendation behind a Brand capability-gap
    proposal -- mirrors influencer.factory.draft_influencer_proposal()
    exactly, reusing opportunity_ranking.cited_evidence() rather than
    recomputing anything."""
    niche = opportunity.marketing_niche or opportunity.product_name
    evidence = cited_evidence(opportunity.category, niche, knowledge)

    if opportunity.recommended_market and evidence:
        rationale = (
            f"Real evidence recommends building a brand around the '{niche}' niche in the "
            f"'{opportunity.recommended_market}' market, based on {len(evidence)} independent source(s)."
        )
    elif opportunity.recommended_market:
        rationale = f"Recommended market '{opportunity.recommended_market}' for a '{niche}' brand (no cited evidence URLs)."
    else:
        rationale = f"No market-specific evidence yet for a '{niche}' brand — category-general recommendation only."

    return BrandDraft(
        recommended_name=opportunity.product_name,
        recommended_niche=niche,
        recommended_category=opportunity.category,
        recommended_market=opportunity.recommended_market,
        source_opportunity_id=opportunity.id,
        rationale=rationale,
        evidence=evidence,
    )


# Curated, transparent, editable starting-point pools -- NOT evidence, NOT
# real generation (no LLM integration exists anywhere in this codebase).
# Selection is deterministic, hashed off source_opportunity_id, the same
# mechanism influencer.factory.suggest_persona() already uses -- the same
# proposal always yields the same suggestion.
TAGLINE_TEMPLATES = [
    "Real {niche}. Real results.",
    "{niche}, made simple.",
    "The honest way to {niche}.",
]

VISUAL_IDENTITIES = [
    "Clean, minimalist, pastel palette — feels trustworthy and approachable.",
    "Bold, high-contrast, energetic colors — feels confident and modern.",
    "Warm, natural tones, soft imagery — feels personal and authentic.",
]

VOICES = [
    "Direct and honest — no hype, explains the real value plainly.",
    "Warm and encouraging — speaks like a knowledgeable friend.",
    "Confident and energetic — short, punchy, benefit-first.",
]


@dataclass
class BrandSuggestion:
    """A creative STARTING POINT for a Brand's tagline/visual_identity/
    voice — the same treatment influencer.factory.PersonaSuggestion
    already established for a Digital Influencer's WHO fields (the
    founder's explicit choice, 2026-08-03): one specific, deterministic,
    clearly-labeled, editable suggestion per field, never evidence, never
    authoritative. Kept as a structurally separate type from BrandDraft."""

    tagline: str
    visual_identity: str
    voice: str


def suggest_brand(draft: BrandDraft) -> BrandSuggestion:
    """Deterministic — reruns of the same BrandDraft (same
    source_opportunity_id) always produce the same suggestion, mirroring
    influencer.factory.suggest_persona()'s reproducibility guarantee."""
    seed = int(hashlib.sha256(draft.source_opportunity_id.encode()).hexdigest(), 16)
    return BrandSuggestion(
        tagline=TAGLINE_TEMPLATES[seed % len(TAGLINE_TEMPLATES)].format(niche=draft.recommended_niche),
        visual_identity=VISUAL_IDENTITIES[seed % len(VISUAL_IDENTITIES)],
        voice=VOICES[seed % len(VOICES)],
    )


def create_brand_from_proposal(
    task_id: str,
    memory: BrainMemory,
    affiliate_store: AffiliateStore,
    knowledge: KnowledgeBase,
    brand_registry: BrandRegistry,
    campaign_registry: CampaignRegistry | None = None,
    name: str | None = None,
    tagline: str | None = None,
    visual_identity: str | None = None,
    voice: str | None = None,
) -> Brand:
    """Materializes a real Brand from an approved Brand Factory proposal —
    mirrors influencer.factory.create_influencer_from_proposal() exactly:
    every WHO-shaped parameter is `None` by default, meaning "use the
    suggestion"; passing an explicit value overrides just that one field.

    Fail-closed the same three ways: raises ValueError if `task_id` isn't
    actually a Brand Factory proposal (checked via TASK_MARKER, not just
    category + source_opportunity_id — a single opportunity can justify
    both a Brand proposal and a Digital Influencer proposal, so those two
    alone can't tell them apart), and raises ValueError if it hasn't
    actually been approved yet (task.status == "done" only after
    CEOBrain.approve() resolves the linked Proposal). Creation can never
    happen before approval.

    When `campaign_registry` is given, auto-links this Brand to the real
    Campaign already running for the same goal (if one exists and doesn't
    already have a brand) — the same direct, explicit linking
    link_destination_url()/link_goal() already do, done here rather than
    forcing the founder to look up and run a separate link command.
    """
    task = memory.get_task(task_id)
    if task.category != "create_asset" or task.source_opportunity_id is None or not task.description.startswith(TASK_MARKER):
        raise ValueError(f"task {task_id!r} is not a Brand Factory proposal")
    if task.status != "done":
        raise ValueError(
            f"task {task_id!r} has not been approved yet (status={task.status!r}) — "
            f"run 'atlas brain approve {task_id}' first"
        )

    opportunity = affiliate_store.get_opportunity(task.source_opportunity_id)
    draft = draft_brand_proposal(opportunity, knowledge)
    suggestion = suggest_brand(draft)

    brand = Brand(
        name=name if name is not None else draft.recommended_name,
        tagline=tagline if tagline is not None else suggestion.tagline,
        visual_identity=visual_identity if visual_identity is not None else suggestion.visual_identity,
        voice=voice if voice is not None else suggestion.voice,
        niche=draft.recommended_niche,
        category=draft.recommended_category,
        market=draft.recommended_market,
        source_opportunity_id=opportunity.id,
    )
    brand_registry.save_brand(brand)

    if campaign_registry is not None:
        for campaign in campaign_registry.campaigns():
            if campaign.goal_id == opportunity.goal_id and campaign.brand_id is None:
                link_brand(campaign.id, brand.id, campaign_registry)

    return brand
