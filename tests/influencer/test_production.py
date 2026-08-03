import pytest

from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.production import add_template, assign_product, generate_content_package, templates_of_kind
from atlas.influencer.registry import InfluencerRegistry


def _registry(tmp_path) -> InfluencerRegistry:
    return InfluencerRegistry(tmp_path / "influencers.json")


def _new_influencer(registry, name="Mira") -> DigitalInfluencer:
    influencer = DigitalInfluencer(identity=IdentityProfile(name=name), categories=["affiliate"])
    registry.save_influencer(influencer)
    return influencer


def test_add_template_rejects_an_unknown_kind(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)

    with pytest.raises(ValueError):
        add_template(influencer.id, "meme_template", "n", "c", registry)


def test_add_template_appends_and_persists(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)

    updated = add_template(influencer.id, "hook", "curiosity hook", "Nobody tells you this about {product_name}...", registry, tags=["fitness"])

    assert len(updated.templates) == 1
    assert updated.templates[0].kind == "hook"
    assert updated.templates[0].tags == ["fitness"]
    assert len(registry.get_influencer(influencer.id).templates) == 1


def test_templates_of_kind_filters_correctly(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)
    add_template(influencer.id, "hook", "h1", "hook one", registry)
    add_template(influencer.id, "cta", "c1", "cta one", registry)
    updated = add_template(influencer.id, "hook", "h2", "hook two", registry)

    assert {t.name for t in templates_of_kind(updated, "hook")} == {"h1", "h2"}
    assert {t.name for t in templates_of_kind(updated, "cta")} == {"c1"}
    assert templates_of_kind(updated, "video_prompt") == []


def test_assign_product_appends_and_persists(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)

    updated = assign_product(influencer.id, "KetoDNA", registry, goal_id="goal-a")

    assert len(updated.product_assignments) == 1
    assert updated.product_assignments[0].product_name == "KetoDNA"
    assert updated.product_assignments[0].goal_id == "goal-a"
    assert updated.product_assignments[0].status == "assigned"
    assert len(registry.get_influencer(influencer.id).product_assignments) == 1


def test_generate_content_package_raises_for_an_unknown_assignment(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)

    with pytest.raises(KeyError):
        generate_content_package(influencer.id, "does-not-exist", registry)


def test_generate_content_package_substitutes_product_name(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)
    add_template(influencer.id, "hook", "h1", "Nobody tells you this about {product_name}...", registry)
    add_template(influencer.id, "cta", "c1", "Try {product_name} today — link in bio.", registry)
    updated = assign_product(influencer.id, "KetoDNA", registry)
    assignment_id = updated.product_assignments[0].id

    package = generate_content_package(influencer.id, assignment_id, registry)

    assert package.hooks == ["Nobody tells you this about KetoDNA..."]
    assert package.ctas == ["Try KetoDNA today — link in bio."]


def test_generate_content_package_leaves_literal_braces_alone_when_not_the_product_name_placeholder(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)
    add_template(influencer.id, "script_template", "s1", "Intro {hook} then pitch {product_name}.", registry)
    updated = assign_product(influencer.id, "KetoDNA", registry)
    assignment_id = updated.product_assignments[0].id

    package = generate_content_package(influencer.id, assignment_id, registry)

    assert package.scripts == ["Intro {hook} then pitch KetoDNA."]


def test_generate_content_package_reports_every_missing_kind_honestly(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)
    add_template(influencer.id, "hook", "h1", "hook about {product_name}", registry)
    updated = assign_product(influencer.id, "KetoDNA", registry)
    assignment_id = updated.product_assignments[0].id

    package = generate_content_package(influencer.id, assignment_id, registry)

    assert "hook" not in package.missing_kinds
    assert "cta" in package.missing_kinds
    assert "script_template" in package.missing_kinds
    assert len(package.missing_kinds) == 7  # every TEMPLATE_KINDS entry except "hook"


def test_generate_content_package_uses_multiple_templates_of_the_same_kind(tmp_path):
    registry = _registry(tmp_path)
    influencer = _new_influencer(registry)
    add_template(influencer.id, "hook", "h1", "hook one about {product_name}", registry)
    add_template(influencer.id, "hook", "h2", "hook two about {product_name}", registry)
    updated = assign_product(influencer.id, "KetoDNA", registry)
    assignment_id = updated.product_assignments[0].id

    package = generate_content_package(influencer.id, assignment_id, registry)

    assert len(package.hooks) == 2
    assert package.hooks == ["hook one about KetoDNA", "hook two about KetoDNA"]
