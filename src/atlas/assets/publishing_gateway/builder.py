from atlas.assets.editorial_review.checks import check_compliance
from atlas.assets.affiliate_department.models import provider_tracking_link

# The Gateway is "the single controlled entry point" — it must not just
# trust upstream stages, it re-verifies independently before anything is
# built. Reuses Editorial Review's own compliance check rather than
# reimplementing disclosure detection a second time.


def build_publish_package(opportunity) -> tuple[dict | None, str]:
    """Runs every required verification (requirements 1-4) and, only if all
    pass, returns the constructed package fields (requirement 5). Returns
    (None, reason) on any failure — fail-closed, never a partially-built
    package."""
    if opportunity.editorial_verdict != "pass":
        return None, f"Editorial verdict is not PASS (got: {opportunity.editorial_verdict!r})"

    if opportunity.stage != "approved_for_marketing":
        return None, f"No founder approval found for this content package (stage: {opportunity.stage!r})"

    disclosed, note = check_compliance(opportunity.content_package, opportunity)
    if not disclosed:
        return None, f"Affiliate disclosure re-verification failed: {note}"

    # Never queue a campaign without a real creative asset attached. A
    # creative *brief* existing (CreativeAgent's draft stage) is not enough —
    # only CreativeAgent.attach_real_asset() (a founder recording a real,
    # actually-produced asset) sets status to "ready".
    if opportunity.creative_assets.get("status") != "ready":
        return None, "No real creative asset attached for this opportunity (creative_assets status is not 'ready')"

    package = opportunity.content_package
    platform_suggestions = package.get("platform_suggestions", [])
    platform = platform_suggestions[0]["platform"] if platform_suggestions else "unspecified"

    headlines = package.get("headlines", [])
    ctas = package.get("ctas", [])
    disclosure_cta = next(
        (cta for cta in ctas if "affiliate" in cta.lower() or "#ad" in cta.lower()),
        ctas[0] if ctas else "",
    )

    product_slug = opportunity.product_name.split(" ")[0].lower().strip("()")
    # Same marketing_niche-over-category fallback as Content Factory's
    # generator — category is the provider's product-type classification
    # (e.g. "software"), not the audience-facing niche. Stripped to
    # alphanumerics since a hashtag can't contain the spaces/slashes a
    # freeform niche string like "Keto Diet / Weight Loss" has.
    niche = opportunity.marketing_niche or opportunity.category
    niche_tag = "".join(ch for ch in niche.lower() if ch.isalnum())
    hashtags = [f"#{niche_tag}", f"#{product_slug}", "#ad"]

    fields = {
        "platform": platform,
        "title": headlines[0] if headlines else opportunity.product_name,
        "description": package.get("campaign_summary", {}).get("why_people_would_buy", ""),
        "cta": ctas[0] if ctas else "",
        "hashtags": hashtags,
        "affiliate_disclosure": disclosure_cta,
        "media_references": [opportunity.creative_assets["reference"]],
        "tracking_link": provider_tracking_link(
            opportunity.provider,
            opportunity.real_affiliate_link,
            opportunity.goal_id or "",
        ),
        "opportunity_id": opportunity.id,
        "goal_id": opportunity.goal_id,
    }
    return fields, "ok"
