from atlas.brain.cashflow import profit
from atlas.brain.memory import BrainMemory
from atlas.brain.kpi import KPIRegistry
from atlas.brain.models import SuccessLaw
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry

# Founder's explicit architectural directives (2026-08-03): "Digital
# Influencers are not marketing assets. They are long-term business
# assets... ATLAS should maximize the lifetime value of every digital
# asset it creates" — then, one level higher: "ATLAS should maintain a
# Business Asset Portfolio... Every reusable asset should have a lifetime
# value that grows over time." This module (renamed from the original
# influencer-only `influencer_value.py` the same day, once a second real
# asset type needed the identical measurement) holds the one real,
# shared "how much has this asset actually earned" mechanism every asset
# type's lifetime-value function is built from — never a second, parallel
# revenue-attribution mechanism per asset type.
#
# Lives in atlas.brain (not atlas.influencer/atlas.brand) because it
# genuinely spans Campaign and multiple asset domains — the same layering
# campaign_advance.py already established (atlas.brain freely imports
# influencer/brand/campaign; those peer packages don't import each other
# except the one documented campaign -> influencer relationship).


def asset_lifetime_value(campaigns_for_asset: list[Campaign], memory: BrainMemory, kpis: KPIRegistry) -> float | None:
    """Real, measured profit summed across a given list of real Campaigns
    — the shared aggregation core behind influencer_lifetime_value() and
    brand_lifetime_value() (and any future asset type's lifetime-value
    function): each supplies a different real "was this asset part of
    this campaign" filter over CampaignRegistry.campaigns(), then this
    does the one real computation both need. Never a fabricated 0.0 for a
    campaign whose profit isn't measured yet — the same fail-closed
    discipline cashflow.profit() itself already enforces. None (never
    0.0) when the asset was part of zero campaigns, or every campaign it
    was part of still has unmeasured profit — an asset with no real
    measured outcome yet has unknown lifetime value, not zero value."""
    relevant_goal_ids = {c.goal_id for c in campaigns_for_asset if c.goal_id}

    profits = []
    for goal_id in relevant_goal_ids:
        try:
            goal = memory.get_goal(goal_id)
        except KeyError:
            continue
        p = profit(goal, kpis)
        if p is not None:
            profits.append(p)

    if not profits:
        return None
    return sum(profits)


def influencer_lifetime_value(
    influencer_id: str, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry
) -> float | None:
    """Real lifetime value of one Digital Influencer, across every real
    Campaign they've ever been part of, regardless of business model/
    category. See asset_lifetime_value() for the shared computation."""
    relevant = [c for c in campaigns.campaigns() if influencer_id in c.influencer_ids]
    return asset_lifetime_value(relevant, memory, kpis)


def brand_lifetime_value(brand_id: str, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry) -> float | None:
    """Real lifetime value of one Brand, across every real Campaign it's
    ever been linked to (Campaign.brand_id), regardless of market. See
    asset_lifetime_value() for the shared computation."""
    relevant = [c for c in campaigns.campaigns() if c.brand_id == brand_id]
    return asset_lifetime_value(relevant, memory, kpis)


def success_law_lifetime_value(law_id: str, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry) -> float | None:
    """Real, measured profit summed across every real Campaign this
    Success Law was relevant/considered for (Campaign.success_law_ids,
    set once at creation time by campaign_advance.py — see
    opportunity_ranking.relevant_success_laws()). Closes the founder's
    "Update Success Laws" loop (2026-08-03) honestly: an ASSOCIATION
    between real outcomes and a law that was in effect, never a causal
    claim that the law *caused* the profit — the exact same "aggregate
    real outcomes, never claim causation" discipline
    confidence.historical_success_score() already applies at category
    level. See asset_lifetime_value() for the shared computation."""
    relevant = [c for c in campaigns.campaigns() if law_id in c.success_law_ids]
    return asset_lifetime_value(relevant, memory, kpis)


def rank_success_laws_by_track_record(
    laws: list[SuccessLaw], campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry
) -> list[SuccessLaw]:
    """Decision Engine reasoning step "Improve the next decision"
    (2026-08-03): re-ranks a list of Success Laws (e.g. from
    opportunity_ranking.relevant_success_laws(), which already ranks by
    evidence quality) by their REAL measured track record —
    success_law_lifetime_value(), real profit across every campaign each
    was relevant for — when one exists. A law with a real, positive
    track record is preferred over one with equal evidence but a
    negative or unmeasured outcome. Python's sort is stable, so laws
    with no measured campaigns yet (tied at "no value") keep the
    relative order they arrived in — the input's own evidence-quality
    ranking is the honest fallback until real outcomes exist to say
    more."""
    def _rank_key(law: SuccessLaw) -> tuple:
        value = success_law_lifetime_value(law.id, campaigns, memory, kpis)
        return (value is not None, value or 0.0)

    return sorted(laws, key=_rank_key, reverse=True)
