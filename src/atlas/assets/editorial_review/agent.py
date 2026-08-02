from dataclasses import asdict

from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH
from atlas.assets.editorial_review.checks import evaluate

MAX_REVISION_CYCLES = 2


class EditorialReviewAgent:
    """Editorial Review operational agent — automatically evaluates every
    Content Factory package before it can reach the founder. Reuses the same
    shared AffiliateOpportunity/AffiliateStore (same store *file* as
    Affiliate Intelligence and Content Factory) rather than a new entity or
    a second state machine.

    Self-contained with respect to atlas.core/atlas.brain; imports from the
    sibling affiliate_department/affiliate_intelligence packages are the
    same deliberate model/store reuse those two already established.
    """

    def __init__(self, store: AffiliateStore | None = None) -> None:
        self._store = store if store is not None else AffiliateStore(DEFAULT_STORE_PATH)

    def run(self, task=None, **kwargs) -> dict:
        if task is not None and getattr(task, "category", None) not in (None, "editorial_review"):
            return {"status": "done", **self._summarize()}

        for opportunity in self._store.opportunities():
            if opportunity.stage == "content_packaged" and not opportunity.editorial_verdict:
                self._evaluate(opportunity)
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    def _evaluate(self, opportunity) -> None:
        result = evaluate(opportunity.content_package, opportunity)
        opportunity.editorial_cycles += 1
        opportunity.editorial_feedback = result
        verdict = result["verdict"]

        if verdict == "pass":
            opportunity.editorial_verdict = "pass"
            opportunity.transition("editorial_passed", "Editorial Review: passed all 7 checks")
        elif verdict == "revision_required" and opportunity.editorial_cycles < MAX_REVISION_CYCLES:
            opportunity.editorial_verdict = "revision_required"
            opportunity.transition(
                "content_packaged",
                f"Editorial Review: revision required (cycle {opportunity.editorial_cycles}/{MAX_REVISION_CYCLES}) — "
                f"failed sections: {result['failed_sections']}",
            )
        else:
            opportunity.editorial_verdict = "reject"
            opportunity.transition(
                "lost",
                f"Editorial Review: rejected after {opportunity.editorial_cycles} cycle(s) — campaign abandoned",
            )
        self._store.save_opportunity(opportunity)

    def _summarize(self) -> dict:
        opportunities = self._store.opportunities()
        by_stage: dict[str, int] = {}
        for o in opportunities:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
        return {"opportunities": [asdict(o) for o in opportunities], "by_stage": by_stage}
