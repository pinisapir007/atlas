from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.content_factory.generator import generate_content_package
from atlas.assets.publishing_gateway.agent import PublishingGatewayAgent
from atlas.assets.publishing_gateway.store import PublishingQueueStore
from atlas.brain.models import Task


def _stores(tmp_path):
    return AffiliateStore(tmp_path / "shared.json"), PublishingQueueStore(tmp_path / "queue.json")


def _approved_opportunity(affiliate_store, **overrides):
    defaults = {
        "product_name": "QuietDesk (ergonomic desk accessories)",
        "description": "",
        "category": "physical_good",
        "commission_per_conversion": 25.0,
        "goal_id": "goal-a",
        "editorial_verdict": "pass",
        "stage": "approved_for_marketing",
        "creative_assets": {"type": "short_video", "status": "ready", "reference": "file:///real/video.mp4"},
    }
    defaults.update(overrides)
    opportunity = AffiliateOpportunity(**defaults)
    opportunity.content_package = generate_content_package(opportunity, include_disclosure=True)
    affiliate_store.save_opportunity(opportunity)
    return opportunity


def test_builds_ready_package_for_approved_opportunity(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    opportunity = _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)

    result = agent.run()

    assert result["by_status"]["READY"] == 1
    package = result["packages"][0]
    assert package["opportunity_id"] == opportunity.id
    assert package["status"] == "READY"


def test_does_not_build_a_second_package_for_the_same_opportunity(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)

    agent.run()
    result = agent.run()

    assert result["by_status"]["READY"] == 1  # still just one, not duplicated


def test_failed_verification_produces_failed_package(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    opportunity = AffiliateOpportunity(
        product_name="Bad",
        description="",
        goal_id="goal-a",
        editorial_verdict="revision_required",  # not "pass" — should fail verification
        stage="approved_for_marketing",
        # Ready creative assets, deliberately, so this test isolates the
        # editorial-verdict failure from the separate creative-asset gate.
        creative_assets={"type": "short_video", "status": "ready", "reference": "file:///real/video.mp4"},
    )
    affiliate_store.save_opportunity(opportunity)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)

    result = agent.run()

    assert result["by_status"]["FAILED"] == 1


def test_approval_dispatch_queues_the_package(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()  # build

    package_id = queue_store.packages()[0].id
    approval_task = Task(
        goal_id="goal-a",
        description="approve queue",
        category="publishing_gateway",
        reversible=False,
        source_opportunity_id=package_id,
    )
    result = agent.run(task=approval_task)

    package = next(p for p in result["packages"] if p["id"] == package_id)
    assert package["status"] == "QUEUED"
    assert any(h["status"] == "APPROVED" for h in package["history"])


def test_cancel_dispatch_cancels_the_package(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()  # build

    package_id = queue_store.packages()[0].id
    cancel_task = Task(
        goal_id="goal-a",
        description="cancel",
        category="publishing_gateway",
        reversible=True,
        source_opportunity_id=package_id,
    )
    result = agent.run(task=cancel_task)

    package = next(p for p in result["packages"] if p["id"] == package_id)
    assert package["status"] == "CANCELLED"


def test_delete_queue_item_removes_it_entirely(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()
    package_id = queue_store.packages()[0].id

    agent.delete_queue_item(package_id)

    assert queue_store.packages() == []


def test_mark_published_transitions_queued_to_published(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()  # build
    package_id = queue_store.packages()[0].id
    approval_task = Task(
        goal_id="goal-a", description="approve queue", category="publishing_gateway",
        reversible=False, source_opportunity_id=package_id,
    )
    agent.run(task=approval_task)  # -> QUEUED

    package = agent.mark_published(package_id)

    assert package.status == "PUBLISHED"
    assert any(h["status"] == "PUBLISHED" for h in package.history)
    assert queue_store.get_package(package_id).status == "PUBLISHED"


def test_mark_published_is_a_no_op_when_not_queued(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()  # build -> READY, never approved to QUEUED
    package_id = queue_store.packages()[0].id

    package = agent.mark_published(package_id)

    assert package.status == "READY"  # unchanged — never re-processed from a non-QUEUED state


def test_does_not_build_or_fail_when_no_real_creative_asset_is_attached(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store, creative_assets={})
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)

    result = agent.run()

    assert result["packages"] == []  # not built yet, and not marked FAILED either -- just not ready


def test_pending_opportunities_excludes_one_without_ready_creative_assets(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store, creative_assets={"type": "short_video", "status": "brief_ready"})
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)

    result = agent.report()

    assert result["pending_opportunities"] == []


def test_builds_once_creative_asset_becomes_ready(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    opportunity = _approved_opportunity(affiliate_store, creative_assets={})
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()
    assert queue_store.packages() == []  # confirm it's genuinely blocked first

    opportunity.creative_assets = {"type": "short_video", "status": "ready", "reference": "file:///real/video.mp4"}
    affiliate_store.save_opportunity(opportunity)
    result = agent.run()

    assert result["by_status"]["READY"] == 1
    assert result["packages"][0]["media_references"] == ["file:///real/video.mp4"]


def test_mismatched_category_task_is_a_safe_no_op(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)

    unrelated = Task(goal_id="goal-a", description="unrelated", category="general")
    result = agent.run(task=unrelated)

    assert result["packages"] == []  # nothing built


def test_report_does_not_mutate_state(tmp_path):
    affiliate_store, queue_store = _stores(tmp_path)
    _approved_opportunity(affiliate_store)
    agent = PublishingGatewayAgent(affiliate_store=affiliate_store, queue_store=queue_store)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after
