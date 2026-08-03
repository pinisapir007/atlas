from atlas.influencer.models import TEMPLATE_KINDS, ContentPackage, ContentTemplate, DigitalInfluencer, ProductAssignment
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


def assign_product(
    influencer_id: str,
    product_name: str,
    registry: InfluencerRegistry,
    goal_id: str | None = None,
    opportunity_id: str | None = None,
) -> DigitalInfluencer:
    """Assigns a real product/opportunity to this influencer for content
    production — a direct, explicit action today. The Decision Engine
    does not call this yet: that wiring is a separate, later increment
    (see atlas.influencer package docs in CLAUDE.md) that touches
    Decision/Goal, both locked, and has no real influencer performance
    history to base an automatic choice on yet."""
    influencer = registry.get_influencer(influencer_id)
    influencer.product_assignments.append(
        ProductAssignment(product_name=product_name, goal_id=goal_id, opportunity_id=opportunity_id)
    )
    registry.save_influencer(influencer)
    return influencer


def generate_content_package(influencer_id: str, product_assignment_id: str, registry: InfluencerRegistry) -> ContentPackage:
    """Assembles a ContentPackage from an influencer's own stored
    templates for a specific product assignment. Deterministic,
    template-based assembly only — the same "no LLM, no external API, no
    image/video/voice generation" boundary content_factory/generator.py
    already established for the affiliate content chain; this is that
    same discipline applied per-influencer instead of globally. The one
    substitution performed is a literal `{product_name}` replacement into
    each template's content — no other placeholder syntax is
    interpreted, so a founder's own literal curly braces in a template
    are never mistaken for a substitution and never raise.

    Any TEMPLATE_KINDS this influencer has no template for is listed in
    the returned package's `missing_kinds` — an honest, visible gap, never
    silently omitted or backfilled with a placeholder asset.
    """
    influencer = registry.get_influencer(influencer_id)
    assignment = next((a for a in influencer.product_assignments if a.id == product_assignment_id), None)
    if assignment is None:
        raise KeyError(f"no such product assignment: {product_assignment_id}")

    def _filled(kind: str) -> list[str]:
        return [t.content.replace(_PRODUCT_NAME_PLACEHOLDER, assignment.product_name) for t in templates_of_kind(influencer, kind)]

    return ContentPackage(
        influencer_id=influencer_id,
        product_assignment_id=product_assignment_id,
        scripts=_filled("script_template"),
        hooks=_filled("hook"),
        ctas=_filled("cta"),
        image_prompts=_filled("image_prompt"),
        video_prompts=_filled("video_prompt"),
        voice_prompts=_filled("voice_prompt"),
        captions=_filled("caption_template"),
        landing_page_messages=_filled("landing_page_message"),
        missing_kinds=sorted(kind for kind in TEMPLATE_KINDS if not templates_of_kind(influencer, kind)),
    )
