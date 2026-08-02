from dataclasses import asdict
from pathlib import Path

from atlas.assets.affiliate_department.models import AffiliateOpportunity, validate_provider_link
from atlas.assets.affiliate_department.scoring import score_opportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agents import DiscoveryAgent, ResearchAgent, RankingAgent

# Reuses AffiliateStore (Mission 003) rather than a second store class —
# same persistence shape, own data file, since Affiliate Intelligence and
# the Affiliate Department are separate departments with separate pipelines.
DEFAULT_STORE_PATH = Path(".atlas/affiliate_intelligence.json")


class AffiliateIntelligenceAgent:
    """Affiliate Intelligence operational agent — composes DiscoveryAgent,
    ResearchAgent, and RankingAgent. Exactly one internal stage advances per
    run() call, the same invariant every stage-machine asset in this
    codebase already documents and relies on (RecruitmentAgent,
    AffiliateDepartmentAgent).

    Self-contained with respect to atlas.core/atlas.brain: no imports from
    either. It does import from the sibling atlas.assets.affiliate_department
    package (the shared Opportunity model, store, and scoring function) —
    a deliberate reuse to avoid a duplicate state machine, not a dependency
    on the orchestration layer.
    """

    def __init__(
        self,
        store: AffiliateStore | None = None,
        discovery: DiscoveryAgent | None = None,
        research: ResearchAgent | None = None,
        ranking: RankingAgent | None = None,
    ) -> None:
        self._store = store if store is not None else AffiliateStore(DEFAULT_STORE_PATH)
        self._discovery = discovery if discovery is not None else DiscoveryAgent()
        self._research = research if research is not None else ResearchAgent()
        self._ranking = ranking if ranking is not None else RankingAgent()

    def run(self, task=None, **kwargs) -> dict:
        if task is not None and getattr(task, "category", None) not in (None, "affiliate_intelligence"):
            # Same safety guard Mission 003 added: an unrelated task landed
            # here via Delegator's unmatched-category fallback must never
            # silently advance this department's pipeline as a side effect.
            return {"status": "done", **self._summarize()}

        opportunity_id = getattr(task, "source_opportunity_id", None)
        if opportunity_id:
            # A founder-choice task (created by affiliate_intelligence_advance
            # with reversible=False) is only ever re-dispatched here via
            # CEOBrain.approve() — CEOBrain.reject() never re-dispatches.
            # Reaching this branch at all means the founder approved it.
            self._mark_selected_for_marketing(opportunity_id)
            return {"status": "done", **self._summarize()}

        opportunities = self._store.opportunities()
        if not opportunities:
            self._run_discovery(task)
        elif any(o.stage == "discovered" for o in opportunities):
            self._run_research()
        elif any(o.stage == "researched" for o in opportunities):
            self._run_ranking()
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    def intake_real_product(
        self,
        *,
        goal_id: str,
        product_name: str,
        description: str,
        category: str,
        commission_per_conversion: float,
        real_affiliate_link: str,
        provider: str,
        provider_product_id: str = "",
        estimated_conversion: float = 0.0,
        competition: float = 0.0,
        content_difficulty: float = 0.0,
    ) -> AffiliateOpportunity:
        """Seeds one real, founder-supplied affiliate opportunity straight
        into 'ranked' — the real-data counterpart to the placeholder
        discover -> research -> rank pipeline. Bypasses ResearchAgent's fixed
        placeholder lookup table entirely (it's keyed by product name and
        would silently zero out real commission/conversion data for any name
        not already in that table) — real inputs are trusted as given, not
        re-derived. Landing at 'ranked' is what makes
        affiliate_intelligence_advance offer this opportunity to the founder
        as a choice on the very next tick, which is the one path that
        actually reaches selected_for_marketing -> Content Factory ->
        Editorial Review -> Publishing Gateway. (AffiliateDepartmentAgent's
        own discovered -> selected -> content_planned pipeline is a separate,
        parallel lifecycle on the same shared model — its founder-approval
        gate does not feed this chain.)
        """
        validate_provider_link(provider, real_affiliate_link)
        opportunity = AffiliateOpportunity(
            product_name=product_name,
            description=description,
            category=category,
            commission_per_conversion=commission_per_conversion,
            estimated_conversion=estimated_conversion,
            competition=competition,
            content_difficulty=content_difficulty,
            real_affiliate_link=real_affiliate_link,
            provider=provider,
            provider_product_id=provider_product_id,
            goal_id=goal_id,
        )
        opportunity.score = score_opportunity(opportunity)
        opportunity.transition(
            "ranked",
            f"Founder intake: real affiliate product via {provider}, ranked directly"
        )
        self._store.save_opportunity(opportunity)
        return opportunity

    def _mark_selected_for_marketing(self, opportunity_id: str) -> None:
        try:
            opportunity = self._store.get_opportunity(opportunity_id)
        except KeyError:
            return
        if opportunity.stage == "ranked":
            opportunity.transition("selected_for_marketing", "Founder approved this opportunity for marketing")
            self._store.save_opportunity(opportunity)

    def _run_discovery(self, task=None) -> None:
        goal_id = getattr(task, "goal_id", None)
        task_id = getattr(task, "id", None)
        for opportunity in self._discovery.discover():
            opportunity.goal_id = goal_id
            opportunity.task_id = task_id
            opportunity.transition("discovered", "DiscoveryAgent: placeholder opportunity, no external source")
            self._store.save_opportunity(opportunity)

    def _run_research(self) -> None:
        for opportunity in self._store.opportunities():
            if opportunity.stage != "discovered":
                continue
            self._research.enrich(opportunity)
            self._store.save_opportunity(opportunity)

    def _run_ranking(self) -> None:
        researched = [o for o in self._store.opportunities() if o.stage == "researched"]
        for opportunity in self._ranking.rank(researched):
            self._store.save_opportunity(opportunity)

    def _summarize(self) -> dict:
        opportunities = self._store.opportunities()
        by_stage = {stage: 0 for stage in ("discovered", "researched", "ranked")}
        for o in opportunities:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
        ranked = sorted(
            (o for o in opportunities if o.stage == "ranked"),
            key=lambda o: o.score,
            reverse=True,
        )
        return {
            "opportunities": [asdict(o) for o in opportunities],
            "by_stage": by_stage,
            "ranked_report": [
                {"rank": i, "product_name": o.product_name, "score": o.score, "notes": o.notes, "id": o.id}
                for i, o in enumerate(ranked, start=1)
            ],
        }
