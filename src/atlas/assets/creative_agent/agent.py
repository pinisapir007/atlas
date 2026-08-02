from dataclasses import asdict

from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH
from atlas.assets.creative_agent.generator import DEFAULT_ASSET_TYPE, generate_creative_brief


class CreativeAgent:
    """Creative Agent operational agent — produces the creative brief for
    each founder-approved campaign, and records a real, founder-supplied
    creative asset once one exists. Reuses the same shared
    AffiliateOpportunity/AffiliateStore (same store file as Affiliate
    Intelligence / Content Factory / Editorial Review / Publishing Gateway),
    not a new entity.

    No real image/video generation happens here — that's a separate,
    explicit future decision (a specific provider + API key). Today this
    agent only drafts a brief and records real assets the founder attaches
    themselves; Publishing Gateway fail-closed refuses to build a package
    until a real asset is attached (see attach_real_asset()).

    Self-contained with respect to atlas.core/atlas.brain. Imports from the
    sibling affiliate_department/affiliate_intelligence packages are the same
    deliberate model/store reuse those packages already established.
    """

    def __init__(self, store: AffiliateStore | None = None) -> None:
        self._store = store if store is not None else AffiliateStore(DEFAULT_STORE_PATH)

    def run(self, task=None, **kwargs) -> dict:
        if task is not None and getattr(task, "category", None) not in (None, "creative_agent"):
            return {"status": "done", **self._summarize()}

        for opportunity in self._store.opportunities():
            if opportunity.stage == "approved_for_marketing" and not opportunity.creative_assets:
                self._draft_brief(opportunity)
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    def attach_real_asset(self, opportunity_id: str, asset_type: str, reference: str) -> AffiliateOpportunity:
        """Direct, non-Task-mediated action — same precedent as
        PublishingGatewayAgent.mark_published/delete_queue_item: recording a
        real-world fact (the founder produced a real asset) is not itself a
        risky action, so it isn't RiskPolicy-gated. This is the only way
        creative_assets["status"] ever becomes "ready"."""
        opportunity = self._store.get_opportunity(opportunity_id)
        assets = dict(opportunity.creative_assets)
        assets["type"] = asset_type
        assets["status"] = "ready"
        assets["reference"] = reference
        opportunity.creative_assets = assets
        self._store.save_opportunity(opportunity)
        return opportunity

    def _draft_brief(self, opportunity) -> None:
        brief = generate_creative_brief(opportunity)
        opportunity.creative_assets = {
            "type": DEFAULT_ASSET_TYPE,
            "status": "brief_ready",
            "brief": brief,
        }
        self._store.save_opportunity(opportunity)

    def _summarize(self) -> dict:
        opportunities = self._store.opportunities()
        by_stage: dict[str, int] = {}
        for o in opportunities:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
        return {"opportunities": [asdict(o) for o in opportunities], "by_stage": by_stage}
