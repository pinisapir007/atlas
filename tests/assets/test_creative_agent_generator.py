from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.content_factory.generator import generate_content_package
from atlas.assets.creative_agent.generator import generate_creative_brief


def _packaged_opportunity():
    opportunity = AffiliateOpportunity(
        product_name="QuietDesk (ergonomic desk accessories)",
        description="",
        category="physical_good",
        commission_per_conversion=25.0,
        goal_id="goal-a",
    )
    opportunity.content_package = generate_content_package(opportunity, include_disclosure=True)
    return opportunity


def test_brief_pulls_hook_headline_and_cta_from_the_content_package():
    opportunity = _packaged_opportunity()

    brief = generate_creative_brief(opportunity)

    assert brief["platform"] in {"TikTok", "Instagram Reels", "Facebook", "Pinterest", "YouTube Shorts"}
    assert brief["voiceover_or_caption"] == opportunity.content_package["hooks"][0]
    assert brief["on_screen_text"] == opportunity.content_package["headlines"][0]
    assert brief["cta_text"] == opportunity.content_package["ctas"][0]


def test_brief_has_a_shot_list_with_positive_total_duration():
    opportunity = _packaged_opportunity()

    brief = generate_creative_brief(opportunity)

    assert len(brief["shots"]) >= 1
    assert all(s["duration_seconds"] > 0 for s in brief["shots"])
    assert brief["estimated_total_seconds"] == sum(s["duration_seconds"] for s in brief["shots"])
