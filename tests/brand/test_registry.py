import pytest

from atlas.brand.models import Brand
from atlas.brand.registry import BrandRegistry, attach_brand_asset


def _registry(tmp_path) -> BrandRegistry:
    return BrandRegistry(tmp_path / "brands.json")


def test_save_and_get_round_trips_every_field(tmp_path):
    registry = _registry(tmp_path)
    brand = Brand(
        name="KetoDNA", tagline="Real keto, real results", visual_identity="clean, pastel, minimalist",
        voice="warm and direct", niche="keto diet", category="affiliate", market="US",
        source_opportunity_id="aopp-1",
    )

    registry.save_brand(brand)
    fetched = registry.get_brand(brand.id)

    assert fetched == brand


def test_brands_lists_every_saved_brand(tmp_path):
    registry = _registry(tmp_path)
    registry.save_brand(Brand(name="A"))
    registry.save_brand(Brand(name="B"))

    names = {b.name for b in registry.brands()}

    assert names == {"A", "B"}


def test_get_brand_raises_for_an_unknown_id(tmp_path):
    registry = _registry(tmp_path)

    with pytest.raises(KeyError, match="no such brand"):
        registry.get_brand("brand-does-not-exist")


def test_brands_is_empty_for_a_fresh_registry(tmp_path):
    registry = _registry(tmp_path)

    assert registry.brands() == []


def test_brand_round_trips_with_an_empty_asset_library_by_default(tmp_path):
    registry = _registry(tmp_path)
    brand = Brand(name="KetoDNA")

    registry.save_brand(brand)

    assert registry.get_brand(brand.id).asset_library == []


# --- attach_brand_asset ------------------------------------------------


def test_attach_brand_asset_records_a_real_reference(tmp_path):
    registry = _registry(tmp_path)
    brand = Brand(name="KetoDNA")
    registry.save_brand(brand)

    updated = attach_brand_asset(brand.id, "logo", "C:/real/logo.png", registry)

    assert len(updated.asset_library) == 1
    assert updated.asset_library[0].asset_type == "logo"
    assert updated.asset_library[0].reference == "C:/real/logo.png"


def test_attach_brand_asset_persists_across_a_fresh_load(tmp_path):
    registry = _registry(tmp_path)
    brand = Brand(name="KetoDNA")
    registry.save_brand(brand)
    attach_brand_asset(brand.id, "logo", "C:/real/logo.png", registry)

    fetched = registry.get_brand(brand.id)

    assert len(fetched.asset_library) == 1
    assert fetched.asset_library[0].reference == "C:/real/logo.png"


def test_attach_brand_asset_supports_multiple_asset_types(tmp_path):
    registry = _registry(tmp_path)
    brand = Brand(name="KetoDNA")
    registry.save_brand(brand)

    attach_brand_asset(brand.id, "logo", "C:/real/logo.png", registry)
    updated = attach_brand_asset(brand.id, "banner", "C:/real/banner.png", registry)

    assert {a.asset_type for a in updated.asset_library} == {"logo", "banner"}


def test_attach_brand_asset_raises_for_an_unknown_brand(tmp_path):
    registry = _registry(tmp_path)

    with pytest.raises(KeyError, match="no such brand"):
        attach_brand_asset("brand-does-not-exist", "logo", "C:/real/logo.png", registry)
