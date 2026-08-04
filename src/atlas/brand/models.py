from dataclasses import asdict, dataclass, field

from atlas.brain.models import new_id, now
from atlas.influencer.models import AssetLibraryEntry


@dataclass
class Brand:
    """The company/product identity a Campaign operates under (2026-08-03,
    Brand Factory) — distinct from a DigitalInfluencer (the persona who
    promotes it) and from Campaign.product_offer (the real, evidence-
    derived product/niche name copied from the AffiliateOpportunity). A
    Brand is the consumer-facing identity wrapper: what it's called, what
    it stands for, how it looks and sounds.

    `niche`/`category`/`market`/`source_opportunity_id` are real,
    structural facts inherited from the real opportunity that justified
    creating this brand — set once via brand.factory.draft_brand_proposal(),
    never guessed. `name`/`tagline`/`visual_identity`/`voice` are the
    founder's final call at creation time — brand.factory.suggest_brand()
    proposes a starting value for each (the same "AI-suggested, clearly
    labeled, always editable" treatment influencer.factory.suggest_persona()
    already established for a Digital Influencer's identity), never
    authoritative on its own.

    `asset_library` (added 2026-08-03, End-to-End Business Execution
    directive) holds real logo/banner/other files once produced — reuses
    AssetLibraryEntry (atlas.influencer.models) rather than a duplicate,
    near-identical dataclass; the same discipline applies here as
    everywhere else it's used: `reference` is always a real file path/URL,
    never a fabricated/generated placeholder. No real logo/banner
    generation integration exists anywhere in this codebase — a founder or
    a real design tool produces the file, `visual_identity` above serves as
    the real creative brief for it, and `brand.registry.attach_brand_asset()`
    records the real result once it exists.
    """

    name: str
    tagline: str = ""
    visual_identity: str = ""
    voice: str = ""
    niche: str = ""
    category: str = ""
    market: str = ""
    source_opportunity_id: str | None = None
    asset_library: list[AssetLibraryEntry] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("brand"))
    created_at: str = field(default_factory=now)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Brand":
        data = dict(data)
        data["asset_library"] = [AssetLibraryEntry(**a) for a in data.get("asset_library", [])]
        return Brand(**data)
