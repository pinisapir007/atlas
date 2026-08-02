from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.content_factory.generator import generate_content_package
from atlas.assets.creative_agent.agent import CreativeAgent
from atlas.brain.models import Task


def _store(tmp_path):
    return AffiliateStore(tmp_path / "shared.json")


def _approved_opportunity(store, **overrides):
    defaults = {
        "product_name": "QuietDesk (ergonomic desk accessories)",
        "description": "",
        "category": "physical_good",
        "commission_per_conversion": 25.0,
        "goal_id": "goal-a",
        "stage": "approved_for_marketing",
    }
    defaults.update(overrides)
    opportunity = AffiliateOpportunity(**defaults)
    opportunity.content_package = generate_content_package(opportunity, include_disclosure=True)
    store.save_opportunity(opportunity)
    return opportunity


def test_drafts_a_brief_for_an_approved_opportunity_with_no_creative_assets_yet(tmp_path):
    store = _store(tmp_path)
    opportunity = _approved_opportunity(store)
    agent = CreativeAgent(store=store)

    result = agent.run()

    updated = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert updated["creative_assets"]["status"] == "brief_ready"
    assert "shots" in updated["creative_assets"]["brief"]


def test_does_not_redraft_once_creative_assets_already_exist(tmp_path):
    store = _store(tmp_path)
    _approved_opportunity(store, creative_assets={"type": "short_video", "status": "ready", "reference": "x"})
    agent = CreativeAgent(store=store)

    result = agent.run()

    assert result["opportunities"][0]["creative_assets"]["status"] == "ready"  # unchanged


def test_attach_real_asset_sets_status_ready_and_reference(tmp_path):
    store = _store(tmp_path)
    opportunity = _approved_opportunity(store)
    agent = CreativeAgent(store=store)
    agent.run()  # draft a brief first

    updated = agent.attach_real_asset(opportunity.id, "short_video", "file:///real/video.mp4")

    assert updated.creative_assets["status"] == "ready"
    assert updated.creative_assets["reference"] == "file:///real/video.mp4"
    assert updated.creative_assets["type"] == "short_video"
    assert "brief" in updated.creative_assets  # preserved, not clobbered


def test_mismatched_category_task_is_a_safe_no_op(tmp_path):
    store = _store(tmp_path)
    _approved_opportunity(store)
    agent = CreativeAgent(store=store)

    unrelated = Task(goal_id="goal-a", description="unrelated", category="general")
    result = agent.run(task=unrelated)

    assert result["opportunities"][0]["creative_assets"] == {}  # untouched


def test_report_does_not_mutate_state(tmp_path):
    store = _store(tmp_path)
    _approved_opportunity(store)
    agent = CreativeAgent(store=store)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after
