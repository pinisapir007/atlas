from dataclasses import dataclass, field

from atlas.brain.asset_value import brand_lifetime_value, influencer_lifetime_value
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.registry import InfluencerRegistry

# The Business Asset Portfolio (2026-08-03): "Digital Influencers are only
# one type of reusable business asset. ATLAS should maintain a Business
# Asset Portfolio... ATLAS should optimize the company's total digital
# asset portfolio, not individual campaigns." This module is a thin,
# read-only VIEW over the real, already-existing per-type registries
# (InfluencerRegistry, BrandRegistry) — never a new, parallel storage
# mechanism, and never a rewrite of either registry. Extending the
# portfolio to a new asset type (Landing Pages, Creative Assets, ...) once
# that type gets its own real top-level model/registry means adding one
# more loop to portfolio_entries(), not touching this module's shape or
# anything that already works.


@dataclass
class PortfolioEntry:
    """One real, reusable business asset, viewed as part of the
    company's total portfolio rather than any single campaign. Purely
    computed on demand by portfolio_entries() from the real registries —
    never persisted on its own, the same read-only-view shape
    ContentPackage/explain_opportunity() already use, since a stored
    entry would silently go stale the moment new evidence or revenue
    arrives.

    `business_models` names the real, founder-declared categories/niche
    this asset already serves today — a structural fact, not a
    historical performance breakdown. `market` is the real market/niche
    it's currently built for. `lifetime_value` (asset_value.py) is the
    one real, measured performance dimension available today; per-market/
    per-platform/per-business-model performance history (what the
    founder's directive also asked for) has no real data source yet
    anywhere in this codebase — deliberately absent here rather than
    fabricated, not a forgotten field."""

    asset_type: str  # "digital_influencer" | "brand" — open string, same convention as Task.category, extensible to future asset types without a schema change
    asset_id: str
    name: str
    market: str
    business_models: list[str] = field(default_factory=list)
    lifetime_value: float | None = None


def portfolio_entries(
    influencers: InfluencerRegistry,
    brands: BrandRegistry,
    campaigns: CampaignRegistry,
    memory: BrainMemory,
    kpis: KPIRegistry,
) -> list[PortfolioEntry]:
    """Every real, active reusable asset ATLAS has created, across every
    asset type that currently has a real top-level model — today, Digital
    Influencers and Brands. Extending this to a future asset type is one
    more loop appended here, never a change to an existing one."""
    entries: list[PortfolioEntry] = []

    for influencer in influencers.influencers():
        if influencer.status != "active":
            continue
        entries.append(
            PortfolioEntry(
                asset_type="digital_influencer",
                asset_id=influencer.id,
                name=influencer.identity.name,
                market=influencer.identity.market,
                business_models=list(influencer.categories),
                lifetime_value=influencer_lifetime_value(influencer.id, campaigns, memory, kpis),
            )
        )

    for brand in brands.brands():
        entries.append(
            PortfolioEntry(
                asset_type="brand",
                asset_id=brand.id,
                name=brand.name,
                market=brand.market,
                business_models=[brand.category] if brand.category else [],
                lifetime_value=brand_lifetime_value(brand.id, campaigns, memory, kpis),
            )
        )

    return entries


def rank_portfolio(entries: list[PortfolioEntry]) -> list[PortfolioEntry]:
    """Ranks the portfolio by real measured lifetime value descending —
    the same None-ranks-lowest, never-crashes discipline
    confidence.rank_by_confidence() already established elsewhere. This is
    the real mechanism behind "optimize the total portfolio, not
    individual campaigns": which real assets are actually earning, across
    every business model and campaign they've ever touched, not just the
    most recent one."""
    return sorted(entries, key=lambda e: (e.lifetime_value is not None, e.lifetime_value or 0.0), reverse=True)
