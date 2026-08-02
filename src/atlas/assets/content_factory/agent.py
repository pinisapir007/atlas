from dataclasses import asdict

from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH
from atlas.assets.content_factory.generator import generate_content_package

REJECTION_LIMIT = 2  # first rejection = "request changes" (regenerate); second = permanent reject
_ACCEPTED_CATEGORIES = (None, "content_factory", "content_factory_editorial_fix")


class ContentFactoryAgent:
    """Content Factory operational agent — generates a complete marketing
    content package for an opportunity the founder already chose in
    Affiliate Intelligence. Reuses AffiliateOpportunity/AffiliateStore
    (Mission 003/005) rather than a new entity, and reuses the exact same
    store *file* Affiliate Intelligence writes to (DEFAULT_STORE_PATH) —
    this must be the same underlying opportunity records, not a second pool.

    Self-contained with respect to atlas.core/atlas.brain. Imports from the
    sibling affiliate_department/affiliate_intelligence packages are a
    deliberate reuse of their model/store, same pattern those two packages
    already established between themselves.
    """

    def __init__(self, store: AffiliateStore | None = None) -> None:
        self._store = store if store is not None else AffiliateStore(DEFAULT_STORE_PATH)

    def run(self, task=None, **kwargs) -> dict:
        if task is not None and getattr(task, "category", None) not in _ACCEPTED_CATEGORIES:
            return {"status": "done", **self._summarize()}

        opportunity_id = getattr(task, "source_opportunity_id", None)
        if opportunity_id:
            self._handle_dispatch_for_opportunity(opportunity_id, task)
            return {"status": "done", **self._summarize()}

        for opportunity in self._store.opportunities():
            if opportunity.stage == "selected_for_marketing" and not opportunity.content_package:
                self._generate(opportunity, variant=0)
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    def _handle_dispatch_for_opportunity(self, opportunity_id: str, task) -> None:
        try:
            opportunity = self._store.get_opportunity(opportunity_id)
        except KeyError:
            return

        if getattr(task, "reversible", None) is False:
            # The founder review task itself, re-dispatched — this only
            # happens via CEOBrain.approve() (CEOBrain.reject() never
            # re-dispatches), so reaching here means the founder approved
            # the package as-is. Founder review only ever triggers after
            # Editorial Review passes it, so the gate here is
            # "editorial_passed", not raw "content_packaged".
            if opportunity.stage == "editorial_passed":
                opportunity.transition("approved_for_marketing", "Founder approved the content package")
                self._store.save_opportunity(opportunity)
            return

        if opportunity.editorial_verdict == "revision_required":
            # Editorial Review asked for a fix — regenerate only the failed
            # sections it named, not the whole package.
            self._fix_failed_sections(opportunity)
            return

        # A regenerate-trigger from a founder rejection (Mission 006) —
        # distinct from an editorial fix: this is "request changes" on an
        # already editorial-approved package, not a pre-review correction.
        opportunity.content_review_rejections += 1
        if opportunity.content_review_rejections >= REJECTION_LIMIT:
            opportunity.transition(
                "lost",
                f"Founder rejected the content package {opportunity.content_review_rejections} times — abandoning this opportunity",
            )
            self._store.save_opportunity(opportunity)
        else:
            self._generate(opportunity, variant=opportunity.content_review_rejections)

    def _generate(self, opportunity, variant: int) -> None:
        opportunity.content_package = generate_content_package(opportunity, variant=variant)
        # A full regeneration is new content — it must go through Editorial
        # Review again from a clean slate, not skip it using a stale verdict
        # from the previous package.
        opportunity.editorial_verdict = ""
        opportunity.editorial_cycles = 0
        opportunity.transition(
            "content_packaged",
            f"Content Factory: package generated (variant {variant}) — planning only, nothing published",
        )
        self._store.save_opportunity(opportunity)

    def _fix_failed_sections(self, opportunity) -> None:
        sections = set(opportunity.editorial_feedback.get("failed_sections", []))
        include_disclosure = "ctas" in sections
        fresh = generate_content_package(
            opportunity, variant=opportunity.editorial_cycles, include_disclosure=include_disclosure
        )
        updated_package = dict(opportunity.content_package)
        for section in sections:
            updated_package[section] = fresh[section]
        opportunity.content_package = updated_package
        opportunity.editorial_verdict = ""  # cleared — ready for a fresh evaluation
        opportunity.transition(
            "content_packaged",
            f"Content Factory: regenerated sections {sorted(sections)} per editorial feedback",
        )
        self._store.save_opportunity(opportunity)

    def _summarize(self) -> dict:
        opportunities = self._store.opportunities()
        by_stage: dict[str, int] = {}
        for o in opportunities:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
        return {"opportunities": [asdict(o) for o in opportunities], "by_stage": by_stage}
