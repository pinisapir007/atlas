import html

from atlas.campaign.models import Campaign
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


def generate_landing_page_html(campaign: Campaign, package: ContentPackage) -> str:
    """Real, deterministic, template-based landing page — closes the
    "Generate the landing page if needed" step of the founder's Cash Flow
    V1 loop (2026-08-03). The same "no LLM, no external API, no
    fabricated content" boundary generate_content_package() already
    established, applied one layer higher: assembles a real, deployable
    static page from real, already-approved copy already on the
    campaign/package — never invents new claims or copy of its own.

    Needs no credentials to generate. Needs a real hosting account to go
    live — that remains a separate, later step (see CLAUDE.md's
    Real-world Connectors gap); this function produces the real artifact
    ready for that account the moment one is connected.

    Fail-closed: raises ValueError if the essential real copy
    (title/description/cta) or a real destination_url isn't present yet
    — a landing page with no real content or nowhere to send traffic
    would be worse than none.
    """
    title = package.titles[0] if package.titles else ""
    description = package.descriptions[0] if package.descriptions else ""
    hook = package.hooks[0] if package.hooks else ""
    cta = package.ctas[0] if package.ctas else ""
    if not (title and description and cta):
        raise ValueError("cannot generate a landing page without real title/description/cta content")
    if not campaign.destination_url:
        raise ValueError("cannot generate a landing page without a real destination_url")

    title_e, description_e, hook_e, cta_e, link_e = (
        html.escape(title), html.escape(description), html.escape(hook), html.escape(cta), html.escape(campaign.destination_url)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title_e}</title>
<meta name="description" content="{description_e}">
</head>
<body>
<h1>{title_e}</h1>
<p>{hook_e}</p>
<p>{description_e}</p>
<a href="{link_e}" rel="nofollow sponsored">{cta_e}</a>
</body>
</html>
"""


def generate_campaign_creative_brief(campaign: Campaign, package: ContentPackage, platform: str = "") -> dict:
    """Real, deterministic creative brief for a Campaign — closes the
    "Generate all required creative assets" step honestly: this is the
    real shot-list a human (or a future real generation provider, a
    separate credentialed decision) works from, not the asset itself. No
    image/video/audio generation happens here — the same boundary
    CreativeAgent.generate_creative_brief() already established for the
    older opportunity-based pipeline; this is its equivalent for the real
    Campaign/ContentPackage pipeline, which had no creative-brief step at
    all until now. Deliberately mirrors that function's shape rather than
    reusing it directly — the two operate on different real data shapes
    (AffiliateOpportunity.content_package vs. Campaign/ContentPackage)
    that aren't safe to silently conflate."""
    hook = package.hooks[0] if package.hooks else ""
    title = package.titles[0] if package.titles else campaign.product_offer
    cta = package.ctas[0] if package.ctas else ""

    shots = [
        {"shot": 1, "duration_seconds": 3, "direction": f'Open on-camera with the hook: "{hook}"'},
        {"shot": 2, "duration_seconds": 15, "direction": f"Show {campaign.product_offer} in real use — demonstrate the real value"},
        {"shot": 3, "duration_seconds": 5, "direction": f'On-screen text: "{title}"'},
        {"shot": 4, "duration_seconds": 4, "direction": f'Close with the CTA, spoken and on-screen: "{cta}"'},
    ]
    return {
        "platform": platform or "unspecified",
        "on_screen_text": title,
        "voiceover_or_caption": hook,
        "cta_text": cta,
        "shots": shots,
        "estimated_total_seconds": sum(s["duration_seconds"] for s in shots),
    }


def assemble_publishing_package(
    campaign_id: str, influencer_id: str, campaign_registry: CampaignRegistry, influencer_registry: InfluencerRegistry
) -> dict:
    """The real, complete bundle everything downstream needs to actually
    publish — copy, real media, landing page, creative brief, tracking
    link — assembled entirely from data that's already real and
    approved. Never generates new business content itself (only calls
    generate_content_package()/generate_landing_page_html()/
    generate_campaign_creative_brief(), all already deterministic and
    template-based). This is the one real artifact "connecting the
    account" or "pressing Approve" is the only thing standing between —
    the same payload a future real ContentPublisher.publish() would
    consume, and exactly what a human needs today to publish manually.

    `landing_page_html` is honestly `None` (never fabricated) when the
    essential copy/link isn't ready yet — mirrors generate_landing_page_html()'s
    own fail-closed behavior rather than raising and blocking the rest of
    the package, since a founder reviewing this package benefits from
    seeing everything that IS ready even if one piece isn't.
    """
    campaign = campaign_registry.get_campaign(campaign_id)
    influencer = influencer_registry.get_influencer(influencer_id)
    package = generate_content_package(campaign_id, influencer_id, campaign_registry, influencer_registry)

    try:
        landing_page_html = generate_landing_page_html(campaign, package)
    except ValueError:
        landing_page_html = None

    platform = influencer.platform_targets[0].platform if influencer.platform_targets else ""

    return {
        "campaign_id": campaign_id,
        "influencer_id": influencer_id,
        "product_offer": campaign.product_offer,
        "destination_url": campaign.destination_url,
        "title": package.titles[0] if package.titles else "",
        "description": package.descriptions[0] if package.descriptions else "",
        "hook": package.hooks[0] if package.hooks else "",
        "cta": package.ctas[0] if package.ctas else "",
        "caption": package.captions[0] if package.captions else "",
        "hashtags": package.hashtags[0] if package.hashtags else "",
        "real_media": [{"type": a.asset_type, "reference": a.reference} for a in influencer.asset_library],
        "platforms": [t.platform for t in influencer.platform_targets],
        "landing_page_html": landing_page_html,
        "creative_brief": generate_campaign_creative_brief(campaign, package, platform=platform),
    }
