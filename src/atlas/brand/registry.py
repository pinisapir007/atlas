from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore
from atlas.brand.models import Brand
from atlas.influencer.models import AssetLibraryEntry


class BrandRegistry:
    """Durable record of every Brand ATLAS has created — pure CRUD, the
    same shape as InfluencerRegistry/CampaignRegistry/KnowledgeBase.
    Domain logic (drafting, suggestion, creation-from-proposal) lives in
    brand.factory, not on this class — same separation every other
    registry in this codebase already draws.
    """

    def __init__(self, path: Path = Path(".atlas/brands.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"brands": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_brand(self, brand: Brand) -> None:
        data = self._read()
        data["brands"][brand.id] = brand.to_dict()
        self._write(data)

    def brands(self) -> list[Brand]:
        return [Brand.from_dict(b) for b in self._read()["brands"].values()]

    def get_brand(self, brand_id: str) -> Brand:
        raw = self._read()["brands"].get(brand_id)
        if raw is None:
            raise KeyError(f"no such brand: {brand_id}")
        return Brand.from_dict(raw)


def attach_brand_asset(brand_id: str, asset_type: str, reference: str, registry: BrandRegistry) -> Brand:
    """Records a real asset (logo, banner, ...) against a brand's asset
    library — same discipline as influencer.registry.attach_asset() and
    CreativeAgent.attach_real_asset(): `reference` is always a real file
    path/URL, never a fabricated/generated placeholder, since no real
    logo/banner/image generation integration exists yet. `Brand.
    visual_identity` is the real creative brief a founder or designer
    works from to produce the file this then records."""
    brand = registry.get_brand(brand_id)
    brand.asset_library.append(AssetLibraryEntry(asset_type=asset_type, reference=reference))
    registry.save_brand(brand)
    return brand
