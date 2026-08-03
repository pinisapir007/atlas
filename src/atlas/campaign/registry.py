from pathlib import Path

from atlas.brain.confidence import confidence_score as compute_confidence_score
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import now
from atlas.brain.store import BrainStore, JSONFileStore
from atlas.campaign.models import Campaign
from atlas.influencer.registry import InfluencerRegistry


class CampaignRegistry:
    """Durable record of every Campaign ATLAS has created — pure CRUD, the
    same shape as InfluencerRegistry/KnowledgeBase/DecisionLog/Ledger.
    Domain logic (assembly, confidence refresh) lives in the free
    functions below, not on this class — same separation every other
    registry in this codebase already draws.
    """

    def __init__(self, path: Path = Path(".atlas/campaigns.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"campaigns": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_campaign(self, campaign: Campaign) -> None:
        data = self._read()
        data["campaigns"][campaign.id] = campaign.to_dict()
        self._write(data)

    def campaigns(self) -> list[Campaign]:
        return [Campaign.from_dict(c) for c in self._read()["campaigns"].values()]

    def get_campaign(self, campaign_id: str) -> Campaign:
        raw = self._read()["campaigns"].get(campaign_id)
        if raw is None:
            raise KeyError(f"no such campaign: {campaign_id}")
        return Campaign.from_dict(raw)


def create_campaign(
    business_objective: str,
    category: str,
    product_offer: str,
    influencer_ids: list[str],
    influencer_registry: InfluencerRegistry,
    knowledge: KnowledgeBase,
    memory: BrainMemory,
    kpis: KPIRegistry,
    registry: CampaignRegistry,
    *,
    revenue_goal: float | None = None,
    target_audience: str = "",
    customer_problem: str = "",
    platform_strategy: str = "",
    content_strategy: str = "",
    content_formats: list[str] | None = None,
    landing_page_strategy: str = "",
    cta_strategy: str = "",
    budget: float | None = None,
    timeline: dict | None = None,
    success_kpis: list[str] | None = None,
    goal_id: str | None = None,
) -> Campaign:
    """Assembles a complete Campaign — the Campaign Intelligence Layer's
    real output, the thing the Decision Engine is meant to eventually
    produce on an "invest" verdict (not yet wired: see
    atlas.campaign package docs in CLAUDE.md for why that's deliberately
    deferred). Every named influencer must already exist in
    influencer_registry — fail-closed, a campaign never references a
    persona that doesn't exist. `confidence_score` reuses the exact
    category-level confidence_score() the Decision Engine's own decide()
    already computes from (Intelligence Layer, unchanged) — never a new,
    parallel scoring mechanism invented just for campaigns.
    """
    known_ids = {i.id for i in influencer_registry.influencers()}
    unknown = [i for i in influencer_ids if i not in known_ids]
    if unknown:
        raise ValueError(f"unknown influencer id(s): {unknown}")

    result = compute_confidence_score(category, knowledge, memory, kpis)
    campaign = Campaign(
        business_objective=business_objective,
        category=category,
        product_offer=product_offer,
        influencer_ids=list(influencer_ids),
        revenue_goal=revenue_goal,
        target_audience=target_audience,
        customer_problem=customer_problem,
        platform_strategy=platform_strategy,
        content_strategy=content_strategy,
        content_formats=content_formats or [],
        landing_page_strategy=landing_page_strategy,
        cta_strategy=cta_strategy,
        budget=budget,
        timeline=timeline or {},
        success_kpis=success_kpis or [],
        confidence_score=result["score"],
        goal_id=goal_id,
    )
    campaign.learning_history.append(
        {"at": now(), "event": "campaign_created", "confidence": result["score"], "factors_available": result["factors_available"]}
    )
    registry.save_campaign(campaign)
    return campaign


def refresh_confidence(campaign_id: str, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry, registry: CampaignRegistry) -> Campaign:
    """Recomputes this campaign's confidence_score from current evidence —
    the campaign-level expression of "nothing is permanently true".
    Appends a learning_history entry recording the change, never silently
    overwriting the prior value without a trace — the same full-
    provenance discipline Decision.superseded_id already enforces for
    Decisions, adapted to a mutable, in-place-updated entity instead of an
    append-only, never-mutated one."""
    campaign = registry.get_campaign(campaign_id)
    previous = campaign.confidence_score
    result = compute_confidence_score(campaign.category, knowledge, memory, kpis)
    campaign.confidence_score = result["score"]
    campaign.learning_history.append(
        {"at": now(), "event": "confidence_refreshed", "previous_confidence": previous, "new_confidence": result["score"]}
    )
    registry.save_campaign(campaign)
    return campaign
