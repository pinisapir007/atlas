from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.content_factory.agent import ContentFactoryAgent
from atlas.brain.models import Task


def _store(tmp_path):
    return AffiliateStore(tmp_path / "shared.json")


def _selected_opportunity(store, **overrides):
    opportunity = AffiliateOpportunity(
        product_name="QuietDesk (ergonomic desk accessories)",
        description="",
        category="physical_good",
        commission_per_conversion=25.0,
        notes="Low competition, easy content angle.",
        stage="selected_for_marketing",
        goal_id="goal-a",
        **overrides,
    )
    store.save_opportunity(opportunity)
    return opportunity


def test_generates_package_for_selected_opportunity(tmp_path):
    store = _store(tmp_path)
    opportunity = _selected_opportunity(store)
    agent = ContentFactoryAgent(store=store)

    result = agent.run()

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "content_packaged"
    assert saved["content_package"]["variant"] == 0
    assert len(saved["content_package"]["hooks"]) >= 10


def test_approval_dispatch_transitions_to_approved(tmp_path):
    store = _store(tmp_path)
    opportunity = _selected_opportunity(store)
    agent = ContentFactoryAgent(store=store)
    agent.run()  # generate

    # Founder review only ever happens after Editorial Review passes it —
    # simulate that having already occurred.
    generated = store.get_opportunity(opportunity.id)
    generated.transition("editorial_passed", "Editorial Review: passed all 7 checks")
    store.save_opportunity(generated)

    approval_task = Task(
        goal_id="goal-a",
        description="review",
        category="content_factory",
        reversible=False,
        source_opportunity_id=opportunity.id,
    )
    result = agent.run(task=approval_task)

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "approved_for_marketing"


def test_first_rejection_regenerates_with_different_variant(tmp_path):
    store = _store(tmp_path)
    opportunity = _selected_opportunity(store)
    agent = ContentFactoryAgent(store=store)
    agent.run()  # generate, variant 0
    first_angles = store.get_opportunity(opportunity.id).content_package["marketing_angles"]

    regenerate_task = Task(
        goal_id="goal-a",
        description="regenerate",
        category="content_factory",
        reversible=True,
        source_opportunity_id=opportunity.id,
    )
    result = agent.run(task=regenerate_task)

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "content_packaged"  # still packaged, ready for another review
    assert saved["content_review_rejections"] == 1
    assert saved["content_package"]["variant"] == 1
    assert saved["content_package"]["marketing_angles"] != first_angles


def test_second_rejection_abandons_the_opportunity(tmp_path):
    store = _store(tmp_path)
    opportunity = _selected_opportunity(store, content_review_rejections=1)
    store.save_opportunity(opportunity)
    agent = ContentFactoryAgent(store=store)
    agent.run()  # generate once so there's a package

    regenerate_task = Task(
        goal_id="goal-a",
        description="regenerate again",
        category="content_factory",
        reversible=True,
        source_opportunity_id=opportunity.id,
    )
    result = agent.run(task=regenerate_task)

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "lost"
    assert saved["content_review_rejections"] == 2


def test_editorial_fix_regenerates_only_named_sections(tmp_path):
    store = _store(tmp_path)
    opportunity = _selected_opportunity(store)
    agent = ContentFactoryAgent(store=store)
    agent.run()  # generate, variant 0, no disclosure

    generated = store.get_opportunity(opportunity.id)
    original_hooks = list(generated.content_package["hooks"])
    original_headlines = list(generated.content_package["headlines"])
    generated.editorial_verdict = "revision_required"
    generated.editorial_cycles = 1
    generated.editorial_feedback = {"failed_sections": ["ctas"]}
    store.save_opportunity(generated)

    fix_task = Task(
        goal_id="goal-a",
        description="fix ctas",
        category="content_factory_editorial_fix",
        reversible=True,
        source_opportunity_id=opportunity.id,
    )
    result = agent.run(task=fix_task)

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "content_packaged"
    assert saved["editorial_verdict"] == ""  # cleared, ready for re-evaluation
    # Only "ctas" was regenerated — everything else is untouched
    assert saved["content_package"]["hooks"] == original_hooks
    assert saved["content_package"]["headlines"] == original_headlines
    assert any("affiliate" in cta.lower() for cta in saved["content_package"]["ctas"])


def test_mismatched_category_task_is_a_safe_no_op(tmp_path):
    store = _store(tmp_path)
    opportunity = _selected_opportunity(store)
    agent = ContentFactoryAgent(store=store)

    unrelated = Task(goal_id="goal-a", description="unrelated", category="general")
    result = agent.run(task=unrelated)

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "selected_for_marketing"  # unchanged


def test_report_does_not_mutate_state(tmp_path):
    store = _store(tmp_path)
    _selected_opportunity(store)
    agent = ContentFactoryAgent(store=store)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after
