import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.campaign.registry import CampaignRegistry, create_campaign
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.production import add_template, generate_campaign_content, generate_content_package, templates_of_kind
from atlas.influencer.registry import InfluencerRegistry


def _influencer_registry(tmp_path) -> InfluencerRegistry:
    return InfluencerRegistry(tmp_path / "influencers.json")


def _campaign_registry(tmp_path) -> CampaignRegistry:
    return CampaignRegistry(tmp_path / "campaigns.json")


def _new_influencer(registry, name="Mira") -> DigitalInfluencer:
    influencer = DigitalInfluencer(identity=IdentityProfile(name=name), categories=["affiliate"])
    registry.save_influencer(influencer)
    return influencer


def _new_campaign(tmp_path, influencer_ids, product_offer="KetoDNA"):
    return create_campaign(
        business_objective="grow affiliate revenue",
        category="affiliate",
        product_offer=product_offer,
        influencer_ids=influencer_ids,
        influencer_registry=_influencer_registry(tmp_path),
        knowledge=KnowledgeBase(tmp_path / "knowledge.json"),
        memory=BrainMemory(tmp_path / "brain.json"),
        kpis=KPIRegistry(BrainMemory(tmp_path / "brain.json")),
        registry=_campaign_registry(tmp_path),
    )


def test_add_template_rejects_an_unknown_kind(tmp_path):
    registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(registry)

    with pytest.raises(ValueError):
        add_template(influencer.id, "meme_template", "n", "c", registry)


def test_add_template_appends_and_persists(tmp_path):
    registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(registry)

    updated = add_template(influencer.id, "hook", "curiosity hook", "Nobody tells you this about {product_name}...", registry, tags=["fitness"])

    assert len(updated.templates) == 1
    assert updated.templates[0].kind == "hook"
    assert updated.templates[0].tags == ["fitness"]
    assert len(registry.get_influencer(influencer.id).templates) == 1


def test_templates_of_kind_filters_correctly(tmp_path):
    registry = _influencer_registry(tmp_path)
    influencer = _new_influencer(registry)
    add_template(influencer.id, "hook", "h1", "hook one", registry)
    add_template(influencer.id, "cta", "c1", "cta one", registry)
    updated = add_template(influencer.id, "hook", "h2", "hook two", registry)

    assert {t.name for t in templates_of_kind(updated, "hook")} == {"h1", "h2"}
    assert {t.name for t in templates_of_kind(updated, "cta")} == {"c1"}
    assert templates_of_kind(updated, "video_prompt") == []


def test_generate_content_package_raises_for_an_influencer_not_on_the_campaign(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    other = _new_influencer(influencer_registry, "Kai")
    campaign = _new_campaign(tmp_path, [influencer.id])

    with pytest.raises(ValueError):
        generate_content_package(campaign.id, other.id, campaign_registry, influencer_registry)


def test_generate_content_package_raises_for_an_unknown_campaign(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)

    with pytest.raises(KeyError):
        generate_content_package("does-not-exist", influencer.id, campaign_registry, influencer_registry)


def test_generate_content_package_substitutes_product_offer_from_the_campaign(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    add_template(influencer.id, "hook", "h1", "Nobody tells you this about {product_name}...", influencer_registry)
    add_template(influencer.id, "cta", "c1", "Try {product_name} today — link in bio.", influencer_registry)
    campaign = _new_campaign(tmp_path, [influencer.id], product_offer="KetoDNA")

    package = generate_content_package(campaign.id, influencer.id, campaign_registry, influencer_registry)

    assert package.hooks == ["Nobody tells you this about KetoDNA..."]
    assert package.ctas == ["Try KetoDNA today — link in bio."]
    assert package.campaign_id == campaign.id
    assert package.influencer_id == influencer.id


def test_generate_content_package_leaves_literal_braces_alone_when_not_the_product_name_placeholder(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    add_template(influencer.id, "script_template", "s1", "Intro {hook} then pitch {product_name}.", influencer_registry)
    campaign = _new_campaign(tmp_path, [influencer.id], product_offer="KetoDNA")

    package = generate_content_package(campaign.id, influencer.id, campaign_registry, influencer_registry)

    assert package.scripts == ["Intro {hook} then pitch KetoDNA."]


def test_generate_content_package_reports_every_missing_kind_honestly(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    add_template(influencer.id, "hook", "h1", "hook about {product_name}", influencer_registry)
    campaign = _new_campaign(tmp_path, [influencer.id])

    package = generate_content_package(campaign.id, influencer.id, campaign_registry, influencer_registry)

    assert "hook" not in package.missing_kinds
    assert "cta" in package.missing_kinds
    assert "script_template" in package.missing_kinds
    assert len(package.missing_kinds) == 7  # every TEMPLATE_KINDS entry except "hook"


def test_generate_content_package_uses_multiple_templates_of_the_same_kind(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    influencer = _new_influencer(influencer_registry)
    add_template(influencer.id, "hook", "h1", "hook one about {product_name}", influencer_registry)
    add_template(influencer.id, "hook", "h2", "hook two about {product_name}", influencer_registry)
    campaign = _new_campaign(tmp_path, [influencer.id])

    package = generate_content_package(campaign.id, influencer.id, campaign_registry, influencer_registry)

    assert len(package.hooks) == 2
    assert package.hooks == ["hook one about KetoDNA", "hook two about KetoDNA"]


def test_generate_campaign_content_produces_one_package_per_assigned_influencer(tmp_path):
    influencer_registry, campaign_registry = _influencer_registry(tmp_path), _campaign_registry(tmp_path)
    mira = _new_influencer(influencer_registry, "Mira")
    kai = _new_influencer(influencer_registry, "Kai")
    add_template(mira.id, "hook", "h1", "Mira's hook about {product_name}", influencer_registry)
    add_template(kai.id, "hook", "h1", "Kai's hook about {product_name}", influencer_registry)
    campaign = _new_campaign(tmp_path, [mira.id, kai.id])

    packages = generate_campaign_content(campaign.id, campaign_registry, influencer_registry)

    assert len(packages) == 2
    by_influencer = {p.influencer_id: p for p in packages}
    assert by_influencer[mira.id].hooks == ["Mira's hook about KetoDNA"]
    assert by_influencer[kai.id].hooks == ["Kai's hook about KetoDNA"]


def test_generate_campaign_content_is_empty_for_a_campaign_with_no_influencers(tmp_path):
    campaign = _new_campaign(tmp_path, [])

    packages = generate_campaign_content(campaign.id, _campaign_registry(tmp_path), _influencer_registry(tmp_path))

    assert packages == []
