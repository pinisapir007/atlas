from atlas.influencer.models import ContentPackage
from atlas.orchestrator.compliance_review import review_content_compliance


def _package(**overrides) -> ContentPackage:
    defaults = dict(influencer_id="influencer-a", campaign_id="campaign-a")
    defaults.update(overrides)
    return ContentPackage(**defaults)


def test_the_real_original_ketodna_defect_fails_review():
    # The exact real, pre-fix content found in production for
    # influencer-38e78ed7e863 / campaign-0044ff398b11 -- fabricated
    # first-person experience, zero AI-persona disclosure.
    package = _package(
        titles=["Why KetoDNA Feels Like a Premium Upgrade, Not Just Another Keto Product"],
        hooks=["I almost scrolled past this... but I'm glad I didn't."],
        descriptions=[
            "I've tried a lot of keto products that promise a lot and deliver very little. "
            "KetoDNA is the first one that actually felt worth switching to — here's my honest, "
            "personal experience with it."
        ],
        ctas=["See why I switched to KetoDNA — link in bio. (affiliate link, I may earn a commission)"],
        captions=["Drop a \U0001f64b if you're tired of keto products that overpromise. My full story + link is in bio."],
    )

    result = review_content_compliance(package)

    assert result.passed is False
    assert any("personal experience" in issue for issue in result.issues)
    assert any("AI/digital-persona disclosure" in issue for issue in result.issues)


def test_the_corrected_ketodna_content_passes_review():
    package = _package(
        titles=["Why KetoDNA Feels Like a Premium Upgrade, Not Just Another Keto Product"],
        hooks=["Confession: this account is AI-curated, not a real person — here's why that's useful."],
        descriptions=[
            "Maya Health is an AI-curated content account, not a personal blog — no fabricated "
            "'my journey.' What you get here is real, checked information about KetoDNA."
        ],
        ctas=["See the real details on KetoDNA — link in bio. (Affiliate link, we may earn a commission.)"],
        captions=["This account is AI-curated — real information, not a personal story. #ad"],
    )

    result = review_content_compliance(package)

    assert result.passed is True
    assert result.issues == []


def test_ai_disclosed_content_is_not_flagged_even_if_it_mentions_a_third_party_experience():
    package = _package(
        descriptions=["This AI-curated account features a real customer's story: 'I tried KetoDNA and...'"],
        ctas=["Link in bio. (affiliate link)"],
    )

    result = review_content_compliance(package)

    assert not any("deception risk" in issue for issue in result.issues)


def test_unsubstantiated_claims_are_flagged():
    package = _package(
        descriptions=["AI-curated content."],
        ctas=["Guaranteed results, a real miracle cure. (affiliate link)"],
    )

    result = review_content_compliance(package)

    assert result.passed is False
    assert any("unsubstantiated" in issue for issue in result.issues)


def test_missing_affiliate_disclosure_is_flagged():
    package = _package(
        descriptions=["AI-curated content, no personal claims here."],
        ctas=["Check it out via the link in bio."],
    )

    result = review_content_compliance(package)

    assert result.passed is False
    assert any("material-connection" in issue for issue in result.issues)


def test_empty_package_fails_on_missing_disclosures_not_a_crash():
    package = _package()

    result = review_content_compliance(package)

    assert result.passed is False
    assert len(result.issues) >= 1
