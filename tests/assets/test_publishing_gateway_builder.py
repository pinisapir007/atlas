from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.content_factory.generator import generate_content_package
from atlas.assets.publishing_gateway.builder import build_publish_package


def _approved_opportunity(include_disclosure=True, creative_ready=True):
    opportunity = AffiliateOpportunity(
        product_name="QuietDesk (ergonomic desk accessories)",
        description="",
        category="physical_good",
        commission_per_conversion=25.0,
        notes="Low competition, easy content angle.",
        goal_id="goal-a",
    )
    opportunity.content_package = generate_content_package(opportunity, include_disclosure=include_disclosure)
    opportunity.editorial_verdict = "pass"
    opportunity.stage = "approved_for_marketing"
    if creative_ready:
        opportunity.creative_assets = {"type": "short_video", "status": "ready", "reference": "file:///real/video.mp4"}
    return opportunity


def test_builds_complete_package_for_a_valid_opportunity():
    opportunity = _approved_opportunity()

    fields, reason = build_publish_package(opportunity)

    assert reason == "ok"
    assert fields["platform"] in {"TikTok", "Instagram Reels", "Facebook", "Pinterest", "YouTube Shorts"}
    assert fields["title"]
    assert fields["description"]
    assert fields["cta"]
    assert len(fields["hashtags"]) >= 1
    assert "affiliate" in fields["affiliate_disclosure"].lower()
    assert fields["media_references"] == ["file:///real/video.mp4"]
    assert fields["opportunity_id"] == opportunity.id
    assert fields["goal_id"] == "goal-a"


def test_rejects_when_no_real_creative_asset_is_attached():
    opportunity = _approved_opportunity(creative_ready=False)

    fields, reason = build_publish_package(opportunity)

    assert fields is None
    assert "creative asset" in reason.lower()


def test_rejects_when_creative_assets_only_has_a_brief_not_a_real_asset():
    opportunity = _approved_opportunity(creative_ready=False)
    opportunity.creative_assets = {"type": "short_video", "status": "brief_ready", "brief": {}}

    fields, reason = build_publish_package(opportunity)

    assert fields is None
    assert "creative asset" in reason.lower()


def test_rejects_when_editorial_verdict_is_not_pass():
    opportunity = _approved_opportunity()
    opportunity.editorial_verdict = "revision_required"

    fields, reason = build_publish_package(opportunity)

    assert fields is None
    assert "Editorial verdict" in reason


def test_rejects_when_founder_approval_stage_is_missing():
    opportunity = _approved_opportunity()
    opportunity.stage = "content_packaged"  # never reached approved_for_marketing

    fields, reason = build_publish_package(opportunity)

    assert fields is None
    assert "founder approval" in reason.lower()


def test_carries_over_the_real_affiliate_link_as_tracking_link():
    opportunity = _approved_opportunity()
    opportunity.real_affiliate_link = "https://real-network.example/track/abc123"

    fields, reason = build_publish_package(opportunity)

    assert reason == "ok"
    assert fields["tracking_link"] == "https://real-network.example/track/abc123"


def test_tracking_link_is_empty_for_a_placeholder_sourced_opportunity():
    opportunity = _approved_opportunity()  # real_affiliate_link left at its "" default

    fields, reason = build_publish_package(opportunity)

    assert reason == "ok"
    assert fields["tracking_link"] == ""


def test_rejects_when_affiliate_disclosure_is_missing():
    opportunity = _approved_opportunity(include_disclosure=False)

    fields, reason = build_publish_package(opportunity)

    assert fields is None
    assert "disclosure" in reason.lower()
