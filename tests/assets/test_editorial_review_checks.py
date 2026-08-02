from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.content_factory.generator import generate_content_package
from atlas.assets.editorial_review.checks import evaluate


def _opportunity(**overrides):
    defaults = dict(
        product_name="QuietDesk (ergonomic desk accessories)",
        description="",
        category="physical_good",
        commission_per_conversion=25.0,
        notes="Low competition, easy content angle.",
    )
    defaults.update(overrides)
    return AffiliateOpportunity(**defaults)


def test_freshly_generated_package_fails_only_compliance():
    opportunity = _opportunity()
    package = generate_content_package(opportunity, variant=0, include_disclosure=False)

    result = evaluate(package, opportunity)

    assert result["verdict"] == "revision_required"
    assert result["checks"]["compliance"]["passed"] is False
    assert result["failed_sections"] == ["ctas"]
    # Every other real, checkable dimension passes on legitimately generated content
    assert result["checks"]["quality"]["passed"] is True
    assert result["checks"]["originality"]["passed"] is True
    assert result["checks"]["cta_quality"]["passed"] is True


def test_package_with_disclosure_passes_compliance_and_overall():
    opportunity = _opportunity()
    package = generate_content_package(opportunity, variant=0, include_disclosure=True)

    result = evaluate(package, opportunity)

    assert result["verdict"] == "pass"
    assert all(check["passed"] for check in result["checks"].values())
    assert result["failed_sections"] == []


def test_unfilled_template_placeholder_fails_quality():
    package = {
        "hooks": ["Struggling with {category} problem"] + ["fine hook " * 3] * 9,
        "headlines": [f"headline {i}" for i in range(10)],
        "campaign_summary": {"product": "QuietDesk"},
        "ctas": ["Try QuietDesk (affiliate link)"],
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["checks"]["quality"]["passed"] is False
    assert "hooks" in result["failed_sections"]


def test_duplicate_headlines_fail_originality():
    package = {
        "hooks": ["a real hook here " * 2] * 10,
        "headlines": ["Same headline"] * 10,
        "campaign_summary": {"product": "QuietDesk"},
        "ctas": ["Try QuietDesk (affiliate link)"],
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["checks"]["originality"]["passed"] is False


def test_wrong_product_name_fails_brand_consistency():
    package = {
        "hooks": ["a real hook here " * 2] * 10,
        "headlines": [f"headline {i}" for i in range(10)],
        "campaign_summary": {"product": "SomeOtherProduct"},
        "ctas": ["Try QuietDesk (affiliate link)"],
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["checks"]["brand_consistency"]["passed"] is False


def test_spam_words_fail_spam_risk():
    package = {
        "hooks": ["GUARANTEED results with QuietDesk!!!"] + ["a real hook here " * 2] * 9,
        "headlines": [f"headline {i}" for i in range(10)],
        "campaign_summary": {"product": "QuietDesk"},
        "ctas": ["Try QuietDesk (affiliate link)"],
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["checks"]["spam_risk"]["passed"] is False


def test_missing_disclosure_fails_compliance_only():
    package = {
        "hooks": ["a real hook here " * 2] * 10,
        "headlines": [f"headline {i}" for i in range(10)],
        "campaign_summary": {"product": "QuietDesk"},
        "ctas": ["Try QuietDesk — link in bio."],
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["checks"]["compliance"]["passed"] is False


def test_cta_without_action_verb_fails_cta_quality():
    package = {
        "hooks": ["a real hook here " * 2] * 10,
        "headlines": [f"headline {i}" for i in range(10)],
        "campaign_summary": {"product": "QuietDesk"},
        "ctas": ["QuietDesk is available now (affiliate link)"],
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["checks"]["cta_quality"]["passed"] is False


def test_three_or_more_failures_reject_instead_of_revision():
    package = {
        "hooks": ["{unfilled} template"],  # fails quality (too few + placeholder)
        "headlines": ["Same"] * 10,  # fails originality
        "campaign_summary": {"product": "Wrong Product"},  # fails brand_consistency
        "ctas": ["QuietDesk available (affiliate link)"],  # fails cta_quality (no verb)
    }
    opportunity = _opportunity(product_name="QuietDesk")

    result = evaluate(package, opportunity)

    assert result["verdict"] == "reject"
