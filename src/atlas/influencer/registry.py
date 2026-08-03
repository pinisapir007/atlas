from pathlib import Path

from atlas.brain.store import BrainStore, JSONFileStore
from atlas.influencer.models import AssetLibraryEntry, DigitalInfluencer, PlatformTarget


class InfluencerRegistry:
    """Durable record of every Digital Influencer ATLAS has created — the
    Digital Influencer Registry. Pure CRUD, the same shape as
    KnowledgeBase/DecisionLog/Ledger: domain logic (ranking, asset
    attachment) lives in separate functions/modules, not on this class.

    Reuses BrainStore/JSONFileStore, the same swappable-backend
    abstraction every other durable store in this codebase already uses.
    """

    def __init__(self, path: Path = Path(".atlas/influencers.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"influencers": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_influencer(self, influencer: DigitalInfluencer) -> None:
        data = self._read()
        data["influencers"][influencer.id] = influencer.to_dict()
        self._write(data)

    def influencers(self) -> list[DigitalInfluencer]:
        return [DigitalInfluencer.from_dict(d) for d in self._read()["influencers"].values()]

    def get_influencer(self, influencer_id: str) -> DigitalInfluencer:
        raw = self._read()["influencers"].get(influencer_id)
        if raw is None:
            raise KeyError(f"no such influencer: {influencer_id}")
        return DigitalInfluencer.from_dict(raw)


def attach_asset(influencer_id: str, asset_type: str, reference: str, registry: InfluencerRegistry) -> DigitalInfluencer:
    """Records a real asset against an influencer's asset library — same
    discipline as CreativeAgent.attach_real_asset(): `reference` is always
    a real file path/URL, never a fabricated/generated placeholder, since
    no real image/video/audio generation integration exists yet."""
    influencer = registry.get_influencer(influencer_id)
    influencer.asset_library.append(AssetLibraryEntry(asset_type=asset_type, reference=reference))
    registry.save_influencer(influencer)
    return influencer


def add_platform_target(influencer_id: str, platform: str, handle: str, registry: InfluencerRegistry) -> DigitalInfluencer:
    """Declares a platform this influencer is meant to operate on —
    structural fact only, never a publish action (Digital Influencer
    Studio does not build platform-specific publishing yet, same boundary
    ContentPublisher already has zero implementations behind)."""
    influencer = registry.get_influencer(influencer_id)
    influencer.platform_targets.append(PlatformTarget(platform=platform, handle=handle))
    registry.save_influencer(influencer)
    return influencer
