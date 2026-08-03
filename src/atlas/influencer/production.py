from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.models import TEMPLATE_KINDS, ContentPackage, ContentTemplate, DigitalInfluencer
from atlas.influencer.registry import InfluencerRegistry

_PRODUCT_NAME_PLACEHOLDER = "{product_name}"


def add_template(
    influencer_id: str, kind: str, name: str, content: str, registry: InfluencerRegistry, tags: list[str] | None = None
) -> DigitalInfluencer:
    """Adds one reusable content template to an influencer's library.
    `kind` must be one of TEMPLATE_KINDS — fail-closed, the same
    discipline get_provider() already applies to an unknown provider
    name, rather than silently accepting an unrecognized library."""
    if kind not in TEMPLATE_KINDS:
        raise ValueError(f"unknown template kind: {kind!r} (must be one of {sorted(TEMPLATE_KINDS)})")
    influencer = registry.get_influencer(influencer_id)
    influencer.templates.append(ContentTemplate(kind=kind, name=name, content=content, tags=tags or []))
    registry.save_influencer(influencer)
    return influencer


def templates_of_kind(influencer: DigitalInfluencer, kind: str) -> list[ContentTemplate]:
    return [t for t in influencer.templates if t.kind == kind]


def generate_content_package(
    campaign_id: str, influencer_id: str, campaign_registry: CampaignRegistry, influencer_registry: InfluencerRegistry
) -> ContentPackage:
    """Assembles one influencer's ContentPackage for a Campaign — the
    Production Layer's real output, generated FROM the Campaign (its
    product_offer + influencer_ids), never from an isolated per-influencer
    assignment (2026-08-03, architecture locked): "The Production Layer
    should generate all required assets from the Campaign, not from
    isolated product assignments" — the founder's framing, verbatim
    intent. Call once per influencer in campaign.influencer_ids for a
    multi-influencer campaign (see generate_campaign_content() below for
    the composed, all-influencers call).

    Deterministic, template-based assembly only — the same "no LLM, no
    external API, no image/video/voice generation" boundary
    content_factory/generator.py already established, applied per-
    influencer instead of globally. The one substitution performed is a
    literal `{product_name}` replacement using campaign.product_offer —
    no other placeholder syntax is interpreted, so a founder's own
    literal curly braces in a template are never mistaken for a
    substitution and never raise.

    Any TEMPLATE_KINDS this influencer has no template for is listed in
    the returned package's `missing_kinds` — an honest, visible gap, never
    silently omitted or backfilled with a placeholder asset.
    """
    campaign = campaign_registry.get_campaign(campaign_id)
    if influencer_id not in campaign.influencer_ids:
        raise ValueError(f"{influencer_id} is not assigned to campaign {campaign_id}")
    influencer = influencer_registry.get_influencer(influencer_id)

    def _filled(kind: str) -> list[str]:
        return [t.content.replace(_PRODUCT_NAME_PLACEHOLDER, campaign.product_offer) for t in templates_of_kind(influencer, kind)]

    return ContentPackage(
        influencer_id=influencer_id,
        campaign_id=campaign_id,
        scripts=_filled("script_template"),
        hooks=_filled("hook"),
        ctas=_filled("cta"),
        image_prompts=_filled("image_prompt"),
        video_prompts=_filled("video_prompt"),
        voice_prompts=_filled("voice_prompt"),
        captions=_filled("caption_template"),
        landing_page_messages=_filled("landing_page_message"),
        titles=_filled("title"),
        descriptions=_filled("description"),
        hashtags=_filled("hashtags"),
        missing_kinds=sorted(kind for kind in TEMPLATE_KINDS if not templates_of_kind(influencer, kind)),
    )


def generate_campaign_content(
    campaign_id: str, campaign_registry: CampaignRegistry, influencer_registry: InfluencerRegistry
) -> list[ContentPackage]:
    """Generates one ContentPackage per influencer assigned to this
    campaign — the composed, whole-campaign call the Production Layer is
    meant to actually be driven by. A thin loop over
    generate_content_package(), not a separate assembly mechanism, so
    there is exactly one place template substitution actually happens."""
    campaign = campaign_registry.get_campaign(campaign_id)
    return [
        generate_content_package(campaign_id, influencer_id, campaign_registry, influencer_registry)
        for influencer_id in campaign.influencer_ids
    ]
