from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.content_factory.generator import MARKETING_ANGLES, generate_content_package


def _opportunity():
    return AffiliateOpportunity(
        product_name="QuietDesk (ergonomic desk accessories)",
        description="",
        category="physical_good",
        commission_per_conversion=25.0,
        notes="Niche physical-good category; low competition and easy content angle.",
    )


def test_generates_required_minimum_counts():
    package = generate_content_package(_opportunity())

    assert len(package["marketing_angles"]) >= 5
    assert len(package["hooks"]) >= 10
    assert len(package["headlines"]) >= 10
    assert len(package["ctas"]) >= 2  # "multiple"
    assert len(package["platform_suggestions"]) >= 5
    assert len(package["content_ideas"]["video"]) >= 10
    assert len(package["content_ideas"]["image"]) >= 10
    assert len(package["content_ideas"]["carousel"]) >= 5


def test_campaign_summary_has_required_fields():
    package = generate_content_package(_opportunity())
    summary = package["campaign_summary"]

    assert set(summary.keys()) == {"product", "audience", "main_problem_solved", "why_people_would_buy"}
    assert summary["product"] == "QuietDesk (ergonomic desk accessories)"


def test_platform_suggestions_each_have_a_reason():
    package = generate_content_package(_opportunity())

    platforms = {entry["platform"] for entry in package["platform_suggestions"]}
    assert platforms == {"TikTok", "Instagram Reels", "Facebook", "Pinterest", "YouTube Shorts"}
    for entry in package["platform_suggestions"]:
        assert entry["reason"]  # every platform has a non-empty explanation
    # At least some reasons are category-specific, not just platform-generic boilerplate
    assert any("physical_good" in entry["reason"] for entry in package["platform_suggestions"])


def test_variant_changes_angle_order_and_selected_ctas():
    base = generate_content_package(_opportunity(), variant=0)
    changed = generate_content_package(_opportunity(), variant=1)

    assert base["marketing_angles"] != changed["marketing_angles"]
    assert base["marketing_angles"][0] != changed["marketing_angles"][0]
    assert set(base["marketing_angles"]) == set(changed["marketing_angles"]) == set(MARKETING_ANGLES)


def test_content_is_parameterized_by_product_not_generic():
    package = generate_content_package(_opportunity())

    assert any("QuietDesk" in hook for hook in package["hooks"])
    assert any("QuietDesk" in headline for headline in package["headlines"])
