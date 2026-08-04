from dataclasses import asdict, dataclass, field

from atlas.brain.models import new_id, now


@dataclass
class IdentityProfile:
    """Who this persona is. `name`/`personality`/`bio` are always the
    founder's final call — there is no real, credentialed generation
    integration anywhere in this codebase (no LLM/image API), the same "no
    fabrication" discipline every other domain here already follows.

    `market` (added 2026-08-03, fixed same day after a live-demo catch)
    holds the real, raw market/country code this influencer was built for
    (e.g. "US", "MX") — the exact same value `AffiliateOpportunity.
    recommended_market`/`Finding.market` use throughout Opportunity
    Discovery, and the field every real matching site (`influencer.
    ranking.prefer_market_match()`, `campaign_advance.
    _missing_market_influencer_task()`/`_find_reusable_influencer()`)
    compares against. `nationality` is the human-readable name for the
    same market (e.g. "American"), derived via the same transparent,
    editable lookup table (`influencer.factory.MARKET_LOCALE`) — for
    display only, never for matching: a name like "American" can never
    equal a code like "US", so code-to-code comparison needs its own real
    field, not a repurposed display one. Both are plain, real-world facts,
    not invented identity details — the same "stated, editable assumption"
    class as `confidence.HASHTAG_PLATFORMS`.

    `age_range` (added 2026-08-03) holds whatever the founder settles on at
    creation time. `influencer.factory.suggest_persona()` proposes a
    starting value for it (and for `name`/`personality`) — explicitly
    labeled a creative suggestion, never evidence, never authoritative —
    the founder's explicit choice (2026-08-03) for how far automation goes
    on fields with no real evidence source. Every one of these stays
    editable/overridable at creation time regardless of where the starting
    value came from."""

    name: str
    language: str = ""
    nationality: str = ""
    market: str = ""
    niche: str = ""  # open string, same convention as Finding.category/Task.category
    personality: str = ""
    age_range: str = ""
    bio: str = ""


@dataclass
class VoiceProfile:
    """How this persona sounds. `provider` names a future voice-synthesis
    platform (e.g. ElevenLabs) — "" until one is actually credentialed and
    integrated, the same credential-boundary discipline
    atlas.integrations already established: naming a provider here is
    free, operating one is a separate, later decision."""

    description: str = ""
    reference_sample: str = ""  # a real audio file path/URL, "" until one exists — never a fabricated sample
    provider: str = ""


@dataclass
class VisualAvatarProfile:
    """What this persona looks like. No real image/video generation
    happens here (same boundary CreativeAgent already draws for real
    business assets) — `reference_image` is a real file path/URL supplied
    by the founder or a real generation provider once one is integrated,
    never a placeholder."""

    description: str = ""
    reference_image: str = ""
    provider: str = ""  # a future avatar-generation provider (e.g. HeyGen/Synthesia) — "" until credentialed


@dataclass
class ContentStyleProfile:
    """How this persona communicates. `posting_cadence` is a stated
    target, not a measured fact — the same class of transparent assumption
    as affiliate_pipeline_advance.ASSUMED_MONTHLY_LEADS, never dressed up
    as real data."""

    tone: str = ""
    format_preferences: list[str] = field(default_factory=list)
    posting_cadence: str = ""


@dataclass
class AudienceProfile:
    """Who this persona is meant to reach. `estimated_size` is None (never
    a fabricated guess-as-fact) until real platform analytics exist — no
    ContentPublisher is implemented yet, so today this is always None in
    practice, honestly."""

    description: str = ""
    target_demographics: dict = field(default_factory=dict)
    estimated_size: float | None = None


@dataclass
class PlatformTarget:
    """One platform this influencer is meant to operate on. `platform` is
    an open string — same convention as PublishPackage.platform — not a
    fixed enum, so a new platform never requires a code change here."""

    platform: str
    handle: str = ""
    status: str = "planned"  # planned | active | paused


@dataclass
class AssetLibraryEntry:
    """One real asset attached to this influencer — a script, image,
    video, or audio file. `reference` is always a real file path/URL,
    never a fabricated/generated placeholder, the same discipline
    CreativeAgent.attach_real_asset() already enforces for campaign
    assets. No real generation integration exists yet, so every entry here
    is either founder-produced or sourced from a real, already-integrated
    provider."""

    asset_type: str  # open string: "script" | "image" | "video" | "audio", ...
    reference: str
    id: str = field(default_factory=lambda: new_id("influencer-asset"))
    created_at: str = field(default_factory=now)


# The Content Production Layer's library kinds (2026-08-03) — an explicit,
# documented, open-but-bounded set, the same discipline
# confidence.CATEGORY_TASK_CATEGORIES already uses, rather than eight
# near-identical dataclasses (ScriptTemplate, Hook, CTA, ...) that would all
# share this exact shape: a name, real founder-authored content, and
# optional matching tags. One kind, one list, one set of functions — a new
# library type is a new string in this set, never a new field/dataclass/
# CLI command.
TEMPLATE_KINDS = {
    "script_template",
    "hook",
    "cta",
    "image_prompt",
    "video_prompt",
    "voice_prompt",
    "caption_template",
    "landing_page_message",
    # Added 2026-08-03 for publish-readiness (see
    # orchestrator.PUBLISH_ESSENTIAL_TEMPLATE_KINDS): "title" and
    # "description" are genuinely distinct from "hook"/"caption_template"
    # for platforms that separate them (e.g. a YouTube title vs. its
    # description), not folded into an existing kind. "hashtags" is its
    # own kind rather than a structured list field, the same reasoning
    # every other template kind already follows — real, founder-authored
    # content, not a fabricated/generated set.
    "title",
    "description",
    "hashtags",
}


@dataclass
class ContentTemplate:
    """One reusable content building block owned by an influencer — a
    script template, hook, CTA, image/video/voice prompt, caption
    template, or landing-page message (`kind`, one of TEMPLATE_KINDS).
    `content` is founder-authored text or a structured prompt string —
    never generated here (no LLM/image/video/voice generation integration
    exists), the same "no real generation, only real founder-authored
    input" boundary content_factory/generator.py and CreativeAgent already
    draw. `tags` are free-form matching hints (e.g. niche or product
    type), founder-set, never inferred."""

    kind: str
    name: str
    content: str
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("template"))
    created_at: str = field(default_factory=now)


@dataclass
class ContentPackage:
    """One assembled set of production-ready assets for a specific
    influencer within a specific Campaign — the Content Production
    Layer's output. Deterministic, template-based assembly from the
    influencer's own stored ContentTemplate library (same "no LLM, no
    external API" boundary content_factory/generator.py already
    established) — never real AI generation, since no such integration
    exists yet. Purely computed on demand (see
    production.generate_content_package()), never persisted — the same
    read-only-view shape explain_opportunity() already has, since a
    stored package would silently go stale the moment the influencer's
    underlying templates (or the campaign's product_offer) change.

    Generated FROM a Campaign (`campaign_id`), never from an isolated
    per-influencer assignment (2026-08-03, architecture locked — the
    now-removed ProductAssignment/`atlas influencer product assign` was
    superseded by Campaign.product_offer + Campaign.influencer_ids, the
    same "one real place this relationship lives" discipline this
    codebase enforces everywhere else, e.g. SUPPORTED_PROVIDERS's
    removal).

    Each field is a list because an influencer may own several templates
    of the same kind; `missing_kinds` names every TEMPLATE_KINDS entry
    this influencer currently has none of — an honest gap surfaced to the
    founder, never silently omitted or filled with a placeholder.
    """

    influencer_id: str
    campaign_id: str
    scripts: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    ctas: list[str] = field(default_factory=list)
    image_prompts: list[str] = field(default_factory=list)
    video_prompts: list[str] = field(default_factory=list)
    voice_prompts: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    landing_page_messages: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    missing_kinds: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("content-package"))
    created_at: str = field(default_factory=now)


@dataclass
class DigitalInfluencer:
    """A reusable digital persona ATLAS can assign to opportunities — the
    Digital Influencer Studio's foundation (2026-08-03, architecture
    locked). Not tied to one platform or one avatar: platform_targets is a
    list, and every sub-profile is generic across TikTok/YouTube/
    Instagram/future platforms alike.

    Composed of five named sub-profiles (identity/voice/visual/
    content_style/audience) plus platform_targets and asset_library — each
    embedded rather than stored separately, since none of them has an
    independent lifecycle apart from the influencer they describe (the
    same reasoning Task.history is embedded rather than its own store).

    `categories` is the explicit, founder-declared set of business
    categories (the same open-string taxonomy Finding.category/
    Task.category already use) this influencer can be assigned to — a
    structural fact declared by the entity itself, the same pattern
    CommerceProvider.category already established, never inferred from
    free-text niche/content_style.

    Performance history is deliberately NOT a field here — real measured
    outcomes live in KPIRegistry (see atlas.influencer.performance), the
    same separation cashflow.py already draws between a Goal and its
    measured revenue/cost. An entity's identity and its measured history
    are different concerns with different mutation patterns (rare
    founder edits vs. frequent real-data updates).

    `templates` is the Content Production Layer's ownership (2026-08-03,
    architecture locked): every reusable production library (script
    templates, hooks, CTAs, image/video/voice prompts, caption templates,
    landing-page messaging) an influencer owns lives here (see
    TEMPLATE_KINDS) — embedded for the same reason platform_targets/
    asset_library are: no independent lifecycle apart from the influencer
    they belong to. Which real product this influencer is producing
    content for is no longer tracked per-influencer (the removed
    ProductAssignment) — that relationship now lives once, on the
    Campaign itself (atlas.campaign.models.Campaign.product_offer +
    influencer_ids), the unit of work every asset is generated from.
    """

    identity: IdentityProfile
    voice: VoiceProfile = field(default_factory=VoiceProfile)
    visual: VisualAvatarProfile = field(default_factory=VisualAvatarProfile)
    content_style: ContentStyleProfile = field(default_factory=ContentStyleProfile)
    audience: AudienceProfile = field(default_factory=AudienceProfile)
    platform_targets: list[PlatformTarget] = field(default_factory=list)
    asset_library: list[AssetLibraryEntry] = field(default_factory=list)
    templates: list[ContentTemplate] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    status: str = "active"  # active | retired
    id: str = field(default_factory=lambda: new_id("influencer"))
    created_at: str = field(default_factory=now)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "DigitalInfluencer":
        """Nested sub-profiles need explicit reconstruction: asdict()
        (used by to_dict()) recurses into plain dicts on the way out, but
        DigitalInfluencer(**data) does not reconstruct dataclasses from
        dicts on the way back in — every other model in this codebase
        (Goal/Task/Finding/Decision/LedgerEntry) is flat and never hits
        this, so the wrinkle is real and specific to this one, deliberately
        nested-by-design model."""
        data = dict(data)
        data["identity"] = IdentityProfile(**data["identity"])
        data["voice"] = VoiceProfile(**data["voice"])
        data["visual"] = VisualAvatarProfile(**data["visual"])
        data["content_style"] = ContentStyleProfile(**data["content_style"])
        data["audience"] = AudienceProfile(**data["audience"])
        data["platform_targets"] = [PlatformTarget(**p) for p in data["platform_targets"]]
        data["asset_library"] = [AssetLibraryEntry(**a) for a in data["asset_library"]]
        data["templates"] = [ContentTemplate(**t) for t in data.get("templates", [])]
        data.pop("product_assignments", None)  # forward-compat: drop the now-removed field from any pre-existing saved influencer
        return DigitalInfluencer(**data)
