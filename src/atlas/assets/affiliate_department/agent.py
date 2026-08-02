from dataclasses import asdict

from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.scoring import score_opportunity
from atlas.assets.affiliate_department.store import AffiliateStore

# Three fixed placeholder candidates — no external source, no internet
# access. Deliberately spread across weak/middling/strong so evaluation has
# something real to discriminate between, not three near-identical entries.
_PLACEHOLDER_OPPORTUNITIES = [
    {
        "product_name": "FocusFlow (productivity SaaS)",
        "description": "A subscription productivity/task app with an affiliate program.",
        "commission_per_conversion": 15.0,
        "estimated_conversion": 0.01,
        "competition": 0.8,
        "content_difficulty": 0.7,
    },
    {
        "product_name": "BudgetWise (personal finance app)",
        "description": "A personal budgeting app with a mid-tier affiliate commission.",
        "commission_per_conversion": 20.0,
        "estimated_conversion": 0.02,
        "competition": 0.5,
        "content_difficulty": 0.5,
    },
    {
        "product_name": "QuietDesk (ergonomic desk accessories)",
        "description": "A niche ergonomic desk-accessory brand with a generous affiliate rate.",
        "commission_per_conversion": 25.0,
        "estimated_conversion": 0.05,
        "competition": 0.2,
        "content_difficulty": 0.2,
    },
]


class AffiliateDepartmentAgent:
    """Affiliate Department operational agent — discovers, evaluates, and
    plans content for affiliate opportunities using placeholder data only.
    No external API, no publishing, no real tracking — exactly one internal
    stage advances per run() call, same invariant RecruitmentAgent already
    documents and relies on.

    Self-contained: no atlas.core/atlas.brain imports, matching every other
    asset in the registry.
    """

    def __init__(self, store: AffiliateStore | None = None) -> None:
        self._store = store if store is not None else AffiliateStore()

    def run(self, task=None, **kwargs) -> dict:
        # Delegator's unmatched-category fallback can hand this agent a task
        # that has nothing to do with the affiliate pipeline (any Triggerable
        # asset is a candidate when no category match exists). Advancing our
        # own internal stage machine as a side effect of an unrelated
        # dispatch would be a real correctness bug, not just a formality —
        # so only actually do anything when the task genuinely belongs here.
        if task is not None and getattr(task, "category", None) not in (None, "affiliate_pipeline"):
            return {"status": "done", **self._summarize()}

        opportunities = self._store.opportunities()
        if not opportunities:
            self._discover(task)
        elif all(o.stage == "discovered" for o in opportunities):
            self._evaluate()
        else:
            for opportunity in self._store.opportunities():
                if opportunity.stage == "selected":
                    self._plan_content(opportunity)
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    # --- Market Intelligence: discovery -------------------------------

    def _discover(self, task=None) -> None:
        goal_id = getattr(task, "goal_id", None)
        task_id = getattr(task, "id", None)
        for entry in _PLACEHOLDER_OPPORTUNITIES:
            opportunity = AffiliateOpportunity(goal_id=goal_id, task_id=task_id, **entry)
            opportunity.transition("discovered", "Market Intelligence: placeholder discovery, no external source")
            self._store.save_opportunity(opportunity)

    # --- Affiliate Manager: evaluate, reject, select --------------------

    def _evaluate(self) -> None:
        opportunities = self._store.opportunities()
        scored = sorted(
            ((o, score_opportunity(o)) for o in opportunities),
            key=lambda pair: pair[1],
            reverse=True,
        )
        best, best_score = scored[0]
        best.score = best_score
        best.transition(
            "selected",
            f"Affiliate Manager: highest score {best_score:.4f} among {len(scored)} evaluated candidates",
        )
        self._store.save_opportunity(best)

        for opportunity, score in scored[1:]:
            opportunity.score = score
            opportunity.transition(
                "lost",
                f"Affiliate Manager: score {score:.4f} below selected candidate's {best_score:.4f}",
            )
            self._store.save_opportunity(opportunity)

    # --- Content Planner (including MAYA Studio, planning only) --------

    def _plan_content(self, opportunity: AffiliateOpportunity) -> None:
        opportunity.content_brief = {
            "audience": f"MAYA's audience segment already interested in {opportunity.category}",
            "hook": f"Why {opportunity.product_name} is worth trying",
            "headline": f"I tried {opportunity.product_name} so you don't have to",
            "cta": f"Try {opportunity.product_name} — link in MAYA's bio",
            "platform": "short-form video",
            "content_ideas": [
                f"Day-in-the-life video featuring {opportunity.product_name}",
                f"Before/after using {opportunity.product_name}",
                f"Q&A addressing common objections to {opportunity.product_name}",
            ],
        }
        opportunity.transition(
            "content_planned",
            "Content Planner / MAYA Studio: brief drafted (planning only — not published)",
        )
        self._store.save_opportunity(opportunity)

    def _summarize(self) -> dict:
        opportunities = self._store.opportunities()
        by_stage = {stage: 0 for stage in ("discovered", "selected", "content_planned", "lost")}
        for o in opportunities:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
        return {
            "opportunities": [asdict(o) for o in opportunities],
            "by_stage": by_stage,
        }
