import hashlib
from dataclasses import dataclass, field

from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunity_ranking import cited_evidence
from atlas.influencer.models import AudienceProfile, ContentStyleProfile, DigitalInfluencer, IdentityProfile, VisualAvatarProfile
from atlas.influencer.registry import InfluencerRegistry

# The Digital Influencer Factory (2026-08-03): ATLAS proposes WHERE and for
# WHAT a new Digital Influencer is justified -- country/language/market and
# niche, both real, evidence-derived facts already computed by Opportunity
# Discovery V1 (opportunity_ranking.py). InfluencerDraft carries ONLY that:
# every field on it is either a citation of real evidence or a plain,
# looked-up fact -- never a fabricated identity detail. That boundary is
# permanent, not a placeholder.
#
# WHO (local name, personality, age range, communication style, visual
# style, preferred platforms) has no real evidence source anywhere in this
# codebase (no demographic data, no LLM/image generation integration). The
# founder's explicit choice (2026-08-03) for that gap: generate one
# specific, clearly-labeled, deterministic, editable suggestion per field
# rather than leave a blank brief -- see PersonaSuggestion/suggest_persona()
# below, kept as a structurally SEPARATE type from InfluencerDraft
# precisely so a real recommendation and a creative suggestion can never be
# confused for each other in code that consumes either.

# Marks every Task this factory creates so create_influencer_from_proposal()
# can tell a real Digital Influencer proposal apart from a Brand Factory
# proposal (see atlas.brand.factory) -- both share Task.category ==
# "create_asset" and can share the same source_opportunity_id (one
# opportunity can justify both), so category + source_opportunity_id alone
# isn't enough to distinguish which factory a given task belongs to.
TASK_MARKER = "Digital Influencer Factory:"

# A real, plain-fact reference table (ISO-style market/country code ->
# nationality + primary native language) -- the same "stated, editable
# assumption" class as confidence.HASHTAG_PLATFORMS, not fabricated
# content: Mexico's primary language really is Spanish, regardless of
# anything ATLAS has measured. Deliberately narrow (only markets this
# codebase has actually seen in real evidence) and deliberately never
# guessed -- a market not listed here yields "" (unknown), never a wrong
# guess dressed as fact. Extend as real markets come up, don't
# pre-populate speculatively.
MARKET_LOCALE = {
    "US": ("American", "English"),
    "GB": ("British", "English"),
    "UK": ("British", "English"),
    "DE": ("German", "German"),
    "FR": ("French", "French"),
    "ES": ("Spanish", "Spanish"),
    "MX": ("Mexican", "Spanish"),
    "BR": ("Brazilian", "Portuguese"),
    "PT": ("Portuguese", "Portuguese"),
    "IT": ("Italian", "Italian"),
    "JP": ("Japanese", "Japanese"),
    "KR": ("South Korean", "Korean"),
    "CN": ("Chinese", "Mandarin Chinese"),
    "IN": ("Indian", "Hindi"),
    "RU": ("Russian", "Russian"),
    "NL": ("Dutch", "Dutch"),
    "CA": ("Canadian", "English"),
    "AU": ("Australian", "English"),
}


@dataclass
class InfluencerDraft:
    """A real, evidence-derived recommendation for where a new Digital
    Influencer is justified -- never a fabricated identity. Every field is
    either a direct citation of real evidence (recommended_market from
    Finding.market, evidence from Finding.evidence), a plain, real-world
    fact looked up from MARKET_LOCALE (nationality, native_language --
    never guessed for an unlisted market), a plain structural fact already
    on the real AffiliateOpportunity that triggered this (recommended_niche,
    recommended_category, source_opportunity_id), or a template built
    purely from those same real fields (recommended_audience). Purely
    computed on demand by draft_influencer_proposal(), never persisted on
    its own -- the same read-only-view shape ContentPackage/
    explain_opportunity() already use, since a stored draft would silently
    go stale the moment new evidence arrives.

    Deliberately absent: name, personality, age range, communication
    style, visual style, preferred platforms -- none of these has a real,
    non-fabricated evidence source anywhere in this codebase today (no
    demographic data, no real image/name generation, no per-platform
    performance data distinct from per-influencer). See PersonaSuggestion/
    suggest_persona() for those -- a structurally separate, explicitly
    labeled creative suggestion, never mixed into this real-evidence
    draft."""

    recommended_market: str
    recommended_niche: str
    recommended_category: str
    source_opportunity_id: str
    rationale: str
    nationality: str = ""
    native_language: str = ""
    recommended_audience: str = ""
    evidence: list[str] = field(default_factory=list)


def draft_influencer_proposal(opportunity: AffiliateOpportunity, knowledge: KnowledgeBase) -> InfluencerDraft:
    """Builds the real recommendation behind a capability-gap proposal —
    reuses opportunity_ranking.cited_evidence() (itself built on
    explain_opportunity_subject()) rather than recomputing anything, the
    same "cite the real mechanism, don't reimplement it" discipline every
    explain-shaped function in this codebase already follows — and the
    same evidence-citing helper brand.factory.draft_brand_proposal() also
    uses, so the extraction logic lives in exactly one place. `niche` falls
    back to product_name when marketing_niche is unset (true for founder-
    manual intake, which has no subject-tagged Finding trail to explain)
    -- evidence/rationale are then honestly empty rather than fabricated."""
    niche = opportunity.marketing_niche or opportunity.product_name
    evidence = cited_evidence(opportunity.category, niche, knowledge)

    if opportunity.recommended_market and evidence:
        rationale = (
            f"Real evidence recommends the '{opportunity.recommended_market}' market for the "
            f"'{niche}' niche, based on {len(evidence)} independent source(s)."
        )
    elif opportunity.recommended_market:
        rationale = f"Recommended market '{opportunity.recommended_market}' for the '{niche}' niche (no cited evidence URLs)."
    else:
        rationale = f"No market-specific evidence yet for the '{niche}' niche — category-general recommendation only."

    nationality, native_language = MARKET_LOCALE.get(opportunity.recommended_market, ("", ""))

    recommended_audience = (
        f"{opportunity.recommended_market} audience interested in {niche}"
        if opportunity.recommended_market
        else f"Audience interested in {niche}"
    )

    return InfluencerDraft(
        recommended_market=opportunity.recommended_market,
        recommended_niche=niche,
        recommended_category=opportunity.category,
        source_opportunity_id=opportunity.id,
        rationale=rationale,
        nationality=nationality,
        native_language=native_language,
        recommended_audience=recommended_audience,
        evidence=evidence,
    )


# Curated, transparent, editable starting-point pools -- NOT evidence, NOT
# real generation (no LLM/image API integration exists anywhere in this
# codebase). Selection is deterministic, hashed off source_opportunity_id,
# so re-deriving a suggestion for the same opportunity always returns the
# same value (reproducible, not randomly regenerated each call) while
# different opportunities can land on different picks. Extend these lists
# as real nationalities/needs come up; a nationality with no dedicated pool
# falls back to _DEFAULT_NAME_POOL rather than guessing a culturally wrong
# name.
NAME_POOLS: dict[str, list[str]] = {
    "American": ["Maya Carter", "Jordan Blake", "Riley Morgan"],
    "British": ["Amelia Clarke", "Oliver Hughes", "Freya Bennett"],
    "German": ["Lena Fischer", "Max Weber", "Anna Schmidt"],
    "French": ["Camille Dubois", "Lucas Martin", "Chloe Bernard"],
    "Spanish": ["Lucia Garcia", "Mateo Fernandez", "Sofia Lopez"],
    "Mexican": ["Sofia Ramirez", "Valentina Torres", "Camila Ruiz"],
    "Brazilian": ["Beatriz Souza", "Gabriel Oliveira", "Isabela Santos"],
    "Portuguese": ["Ines Costa", "Joao Silva", "Matilde Pereira"],
    "Italian": ["Giulia Romano", "Marco Ferrari", "Sofia Russo"],
    "Japanese": ["Yui Tanaka", "Haruto Sato", "Aoi Suzuki"],
    "South Korean": ["Ji-woo Kim", "Min-jun Lee", "Seo-yeon Park"],
    "Chinese": ["Mei Chen", "Wei Zhang", "Xin Liu"],
    "Indian": ["Ananya Sharma", "Arjun Patel", "Diya Reddy"],
    "Russian": ["Anastasia Ivanova", "Dmitri Petrov", "Ekaterina Sokolova"],
    "Dutch": ["Sanne de Jong", "Daan Bakker", "Fenna Visser"],
    "Canadian": ["Emma Tremblay", "Liam Roy", "Olivia Gagnon"],
    "Australian": ["Charlotte Ryan", "Jack Mitchell", "Ava Cooper"],
}
_DEFAULT_NAME_POOL = ["Alex Rivera", "Sam Parker", "Jamie Reed"]

AGE_RANGES = ["22-28", "25-34", "30-40"]

COMMUNICATION_STYLES = [
    "Casual, first-person, testimonial-style — speaks like a friend sharing a real experience, not reading an ad.",
    "Warm and conversational — explains things simply, leads with empathy before the pitch.",
    "Energetic and direct — quick, confident delivery, gets to the point fast.",
]

VISUAL_STYLES = [
    "Natural lighting, everyday setting, minimal production — feels authentic, not corporate.",
    "Clean and simple — plain background, close-up talking-to-camera framing.",
    "Bright and casual — lifestyle setting (kitchen, living room, outdoors), handheld-camera feel.",
]

# A default short-form-first set (consumer testimonial content performs
# best there today, per the same real pilot this whole pipeline was built
# from) -- a stated, editable default, not per-niche evidence (no real
# per-platform performance data exists yet to justify varying it by niche).
PLATFORM_SUGGESTIONS = ["TikTok", "Instagram"]


@dataclass
class PersonaSuggestion:
    """A creative STARTING POINT for the fields InfluencerDraft
    deliberately never includes — local_name, personality, age_range,
    communication_style, visual_style, preferred_platforms. The founder's
    explicit choice (2026-08-03): generate one specific, clearly-labeled,
    editable suggestion per field rather than leave a blank brief. None of
    this is evidence-based or a measured fact — every field here is a
    deterministic, transparent, curated suggestion (see NAME_POOLS etc.),
    always subject to founder review/override before creation. Kept as a
    structurally separate type from InfluencerDraft so a real,
    evidence-grounded recommendation and a creative suggestion can never
    be confused for each other by anything that consumes either."""

    local_name: str
    personality: str
    age_range: str
    communication_style: str
    visual_style: str
    preferred_platforms: list[str] = field(default_factory=list)


def suggest_persona(draft: InfluencerDraft) -> PersonaSuggestion:
    """Deterministic — reruns of the same InfluencerDraft (same
    source_opportunity_id) always produce the same suggestion, so approving
    a proposal and creating from it later never surprises the founder with
    a different draft than the one they saw. `draft.nationality` selects a
    culturally-appropriate name pool when a real one is known
    (MARKET_LOCALE); an unlisted/unknown nationality falls back to a
    neutral default pool rather than guessing wrong."""
    seed = int(hashlib.sha256(draft.source_opportunity_id.encode()).hexdigest(), 16)
    name_pool = NAME_POOLS.get(draft.nationality, _DEFAULT_NAME_POOL)

    return PersonaSuggestion(
        local_name=name_pool[seed % len(name_pool)],
        personality=(
            f"Warm, first-person, relatable — shares real experience with {draft.recommended_niche} "
            "rather than lecturing about it."
        ),
        age_range=AGE_RANGES[seed % len(AGE_RANGES)],
        communication_style=COMMUNICATION_STYLES[seed % len(COMMUNICATION_STYLES)],
        visual_style=VISUAL_STYLES[seed % len(VISUAL_STYLES)],
        preferred_platforms=list(PLATFORM_SUGGESTIONS),
    )


def create_influencer_from_proposal(
    task_id: str,
    memory: BrainMemory,
    affiliate_store: AffiliateStore,
    knowledge: KnowledgeBase,
    influencer_registry: InfluencerRegistry,
    name: str | None = None,
    personality: str | None = None,
    age_range: str | None = None,
    communication_style: str | None = None,
    visual_style: str | None = None,
    bio: str = "",
) -> DigitalInfluencer:
    """Materializes a real DigitalInfluencer from an approved Digital
    Influencer Factory proposal (see campaign_advance._missing_market_
    influencer_task()) — ATLAS proposes WHERE/WHAT (market/nationality/
    native_language/niche/category/audience, all real evidence or plain
    looked-up fact via draft_influencer_proposal()) and a labeled, editable
    starting suggestion for WHO (name/personality/age_range/
    communication_style/visual_style, via suggest_persona() — the
    founder's explicit choice, 2026-08-03, for fields with no real evidence
    source). Every WHO parameter here is `None` by default, meaning "use
    the suggestion" — pass an explicit value to override any single field;
    the rest still fall back to their suggested value, not to "". `bio` has
    no suggestion (not one of the founder's requested fields) and stays
    ""-by-default, founder-only.

    Fail-closed on both ways this could go wrong: raises ValueError if
    `task_id` isn't actually a Factory proposal (no source_opportunity_id,
    or not a create_asset task), and raises ValueError if it hasn't
    actually been approved yet — task.status only reaches "done" once
    CEOBrain.approve() has resolved the linked Proposal (see brain/ceo.py).
    Creation can never happen before approval; this is what enforces "waiting
    for Founder approval before creation" in code, not just in a docstring.
    """
    task = memory.get_task(task_id)
    if task.category != "create_asset" or task.source_opportunity_id is None or not task.description.startswith(TASK_MARKER):
        raise ValueError(f"task {task_id!r} is not a Digital Influencer Factory proposal")
    if task.status != "done":
        raise ValueError(
            f"task {task_id!r} has not been approved yet (status={task.status!r}) — "
            f"run 'atlas brain approve {task_id}' first"
        )

    opportunity = affiliate_store.get_opportunity(task.source_opportunity_id)
    draft = draft_influencer_proposal(opportunity, knowledge)
    persona = suggest_persona(draft)

    influencer = DigitalInfluencer(
        identity=IdentityProfile(
            name=name if name is not None else persona.local_name,
            language=draft.native_language,
            nationality=draft.nationality,
            market=draft.recommended_market,
            niche=draft.recommended_niche,
            personality=personality if personality is not None else persona.personality,
            age_range=age_range if age_range is not None else persona.age_range,
            bio=bio,
        ),
        content_style=ContentStyleProfile(
            tone=communication_style if communication_style is not None else persona.communication_style
        ),
        visual=VisualAvatarProfile(
            description=visual_style if visual_style is not None else persona.visual_style
        ),
        audience=AudienceProfile(description=draft.recommended_audience),
        categories=[draft.recommended_category] if draft.recommended_category else [],
    )
    influencer_registry.save_influencer(influencer)
    return influencer
