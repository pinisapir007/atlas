from dataclasses import asdict

from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH
from atlas.assets.publishing_gateway.builder import build_publish_package
from atlas.assets.publishing_gateway.models import STATUSES, PublishPackage
from atlas.assets.publishing_gateway.store import PublishingQueueStore


class PublishingGatewayAgent:
    """Publishing Gateway operational agent — the single controlled entry
    point between ATLAS and external platforms. Reads opportunities from the
    shared AffiliateOpportunity store (same file as Affiliate Intelligence /
    Content Factory / Editorial Review), builds a PublishPackage into its
    own queue store once every verification passes, and stops — no
    external API is ever called, nothing is ever actually published.

    Self-contained with respect to atlas.core/atlas.brain. The Task
    correlation field `source_opportunity_id` is reused here to carry a
    PublishPackage id once a package exists (a generic "what this dispatch
    is about" reference, not literally always an opportunity) — the same
    field, reused for a second purpose rather than adding another one.
    """

    def __init__(self, affiliate_store: AffiliateStore | None = None, queue_store: PublishingQueueStore | None = None) -> None:
        self._affiliate_store = affiliate_store if affiliate_store is not None else AffiliateStore(DEFAULT_STORE_PATH)
        self._queue_store = queue_store if queue_store is not None else PublishingQueueStore()

    def run(self, task=None, **kwargs) -> dict:
        if task is not None and getattr(task, "category", None) not in (None, "publishing_gateway"):
            return {"status": "done", **self._summarize()}

        reference_id = getattr(task, "source_opportunity_id", None)
        if reference_id:
            self._handle_dispatch(reference_id, task)
            return {"status": "done", **self._summarize()}

        already_packaged_ids = {p.opportunity_id for p in self._queue_store.packages()}
        for opportunity in self._affiliate_store.opportunities():
            if (
                opportunity.stage == "approved_for_marketing"
                and opportunity.id not in already_packaged_ids
                and opportunity.creative_assets.get("status") == "ready"
            ):
                self._build(opportunity)
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    def delete_queue_item(self, package_id: str) -> None:
        """Direct, non-Task-mediated action — same precedent as
        RecruitmentAgent's approve_outreach/mark_lost: a housekeeping action
        with no external effect doesn't need a RiskPolicy gate."""
        self._queue_store.delete_package(package_id)

    def mark_published(self, package_id: str) -> PublishPackage:
        """Records that the founder actually posted this package in the real
        world — a fact, not an action ATLAS performs. Same
        not-RiskPolicy-gated precedent as delete_queue_item: the real,
        irreversible act (going public) already happened by the founder's own
        hand; this only logs it. Only valid from QUEUED — never re-processed
        once already PUBLISHED."""
        package = self._queue_store.get_package(package_id)
        if package.status == "QUEUED":
            package.transition("PUBLISHED", "Founder confirmed this package was posted")
            self._queue_store.save_package(package)
        return package

    def _build(self, opportunity) -> None:
        fields, reason = build_publish_package(opportunity)
        if fields is None:
            package = PublishPackage(
                platform="unspecified",
                title=opportunity.product_name,
                description="",
                cta="",
                opportunity_id=opportunity.id,
                goal_id=opportunity.goal_id,
            )
            package.transition("FAILED", reason)
        else:
            package = PublishPackage(**fields)
            package.transition("READY", "Publishing Gateway: all verifications passed")
        self._queue_store.save_package(package)

    def _handle_dispatch(self, package_id: str, task) -> None:
        try:
            package = self._queue_store.get_package(package_id)
        except KeyError:
            return

        if package.status != "READY":
            return  # already resolved — never re-process

        if getattr(task, "reversible", None) is False:
            # Re-dispatched only via CEOBrain.approve() — reject() never
            # re-dispatches — so reaching here means the founder approved
            # queuing this package.
            package.transition("APPROVED", "Founder approved queuing this package")
            package.transition("QUEUED", "Publishing Gateway: added to the publishing queue (no publish integration exists)")
        else:
            # A cancel-trigger, created after the founder rejected the
            # approve-queue task.
            package.transition("CANCELLED", "Founder cancelled this package")
        self._queue_store.save_package(package)

    def _summarize(self) -> dict:
        packages = self._queue_store.packages()
        by_status = {status: 0 for status in STATUSES}
        for p in packages:
            by_status[p.status] = by_status.get(p.status, 0) + 1

        packaged_opportunity_ids = {p.opportunity_id for p in packages}
        pending_opportunities = [
            {"id": o.id, "goal_id": o.goal_id}
            for o in self._affiliate_store.opportunities()
            if o.stage == "approved_for_marketing"
            and o.id not in packaged_opportunity_ids
            and o.creative_assets.get("status") == "ready"
        ]
        return {
            "packages": [asdict(p) for p in packages],
            "by_status": by_status,
            "pending_opportunities": pending_opportunities,
        }
