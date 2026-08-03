import pytest

from atlas.influencer.models import (
    AudienceProfile,
    ContentStyleProfile,
    ContentTemplate,
    DigitalInfluencer,
    IdentityProfile,
    PlatformTarget,
    VisualAvatarProfile,
    VoiceProfile,
)
from atlas.influencer.registry import InfluencerRegistry, add_platform_target, attach_asset


def _influencer(name="Mira", categories=None) -> DigitalInfluencer:
    return DigitalInfluencer(
        identity=IdentityProfile(name=name, language="en", niche="fitness", personality="energetic, direct"),
        categories=categories or [],
    )


def test_round_trips_a_minimal_influencer(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = _influencer()
    registry.save_influencer(influencer)

    reloaded = InfluencerRegistry(tmp_path / "influencers.json").get_influencer(influencer.id)
    assert reloaded.identity.name == "Mira"
    assert reloaded.identity.niche == "fitness"
    assert reloaded.status == "active"


def test_round_trips_every_sub_profile_and_nested_list(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = DigitalInfluencer(
        identity=IdentityProfile(name="Kai", language="en", niche="personal_finance", personality="calm, analytical", bio="explains money simply"),
        voice=VoiceProfile(description="warm, conversational", reference_sample="https://example.com/voice.mp3", provider="elevenlabs"),
        visual=VisualAvatarProfile(description="modern minimalist", reference_image="https://example.com/avatar.png", provider="heygen"),
        content_style=ContentStyleProfile(tone="educational", format_preferences=["short-form video", "carousel"], posting_cadence="daily"),
        audience=AudienceProfile(description="young professionals", target_demographics={"age_range": "25-34"}, estimated_size=50000.0),
        platform_targets=[PlatformTarget(platform="TikTok", handle="@kai.money", status="active")],
        templates=[ContentTemplate(kind="hook", name="h1", content="hook about {product_name}", tags=["finance"])],
        categories=["affiliate", "digital_product"],
    )
    registry.save_influencer(influencer)

    reloaded = InfluencerRegistry(tmp_path / "influencers.json").get_influencer(influencer.id)
    assert reloaded.voice.provider == "elevenlabs"
    assert reloaded.visual.reference_image == "https://example.com/avatar.png"
    assert reloaded.content_style.format_preferences == ["short-form video", "carousel"]
    assert reloaded.audience.estimated_size == 50000.0
    assert reloaded.templates[0].kind == "hook"
    assert reloaded.templates[0].tags == ["finance"]
    assert reloaded.platform_targets[0].platform == "TikTok"
    assert reloaded.platform_targets[0].status == "active"
    assert reloaded.categories == ["affiliate", "digital_product"]


def test_voice_and_visual_provider_default_to_blank_until_credentialed(tmp_path):
    influencer = _influencer()

    assert influencer.voice.provider == ""
    assert influencer.visual.provider == ""


def test_audience_estimated_size_defaults_to_none_never_a_fabricated_guess(tmp_path):
    influencer = _influencer()

    assert influencer.audience.estimated_size is None


def test_influencers_lists_every_saved_influencer(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    registry.save_influencer(_influencer("Mira"))
    registry.save_influencer(_influencer("Kai"))

    names = {i.identity.name for i in registry.influencers()}
    assert names == {"Mira", "Kai"}


def test_from_dict_drops_the_removed_product_assignments_field_for_backward_compatibility(tmp_path):
    influencer = _influencer()
    stale_data = influencer.to_dict()
    stale_data["product_assignments"] = [{"product_name": "old", "id": "assignment-x"}]  # pre-Campaign saved shape

    reloaded = DigitalInfluencer.from_dict(stale_data)

    assert reloaded.identity.name == "Mira"
    assert not hasattr(reloaded, "product_assignments")


def test_missing_influencer_raises_keyerror(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    with pytest.raises(KeyError):
        registry.get_influencer("does-not-exist")


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "influencers.json"
    registry = InfluencerRegistry(path)
    registry.save_influencer(_influencer())

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()


def test_attach_asset_appends_a_real_reference_to_the_asset_library(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = _influencer()
    registry.save_influencer(influencer)

    updated = attach_asset(influencer.id, "script", "https://example.com/script-1.txt", registry)

    assert len(updated.asset_library) == 1
    assert updated.asset_library[0].asset_type == "script"
    assert updated.asset_library[0].reference == "https://example.com/script-1.txt"
    # persisted, not just returned in-memory
    assert len(registry.get_influencer(influencer.id).asset_library) == 1


def test_attach_asset_accumulates_multiple_real_assets(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = _influencer()
    registry.save_influencer(influencer)

    attach_asset(influencer.id, "script", "ref-1", registry)
    updated = attach_asset(influencer.id, "video", "ref-2", registry)

    assert [a.asset_type for a in updated.asset_library] == ["script", "video"]


def test_add_platform_target_appends_a_new_target(tmp_path):
    registry = InfluencerRegistry(tmp_path / "influencers.json")
    influencer = _influencer()
    registry.save_influencer(influencer)

    updated = add_platform_target(influencer.id, "YouTube", "@mira.fit", registry)

    assert len(updated.platform_targets) == 1
    assert updated.platform_targets[0].platform == "YouTube"
    assert updated.platform_targets[0].handle == "@mira.fit"
    assert updated.platform_targets[0].status == "planned"  # declared, not yet active — no publishing happens here
