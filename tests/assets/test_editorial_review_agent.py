from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.editorial_review.agent import EditorialReviewAgent
from atlas.brain.models import Task


def _store(tmp_path):
    return AffiliateStore(tmp_path / "shared.json")


def _packaged_opportunity(store, content_package, **overrides):
    fields = dict(
        product_name="QuietDesk",
        description="",
        category="physical_good",
        stage="content_packaged",
        content_package=content_package,
        goal_id="goal-a",
    )
    fields.update(overrides)
    opportunity = AffiliateOpportunity(**fields)
    store.save_opportunity(opportunity)
    return opportunity


_GOOD_PACKAGE = {
    "hooks": ["a real hook here " * 2] * 10,
    "headlines": [f"headline {i}" for i in range(10)],
    "campaign_summary": {"product": "QuietDesk"},
    "ctas": ["Try QuietDesk (affiliate link)"],
}

_MISSING_DISCLOSURE_PACKAGE = {
    "hooks": ["a real hook here " * 2] * 10,
    "headlines": [f"headline {i}" for i in range(10)],
    "campaign_summary": {"product": "QuietDesk"},
    "ctas": ["Try QuietDesk — link in bio."],
}

_BADLY_BROKEN_PACKAGE = {
    "hooks": ["{unfilled}"],
    "headlines": ["Same"] * 10,
    "campaign_summary": {"product": "Wrong Product"},
    "ctas": ["QuietDesk available (affiliate link)"],
}


def test_passing_package_transitions_to_editorial_passed(tmp_path):
    store = _store(tmp_path)
    opportunity = _packaged_opportunity(store, _GOOD_PACKAGE)
    agent = EditorialReviewAgent(store=store)

    result = agent.run()

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "editorial_passed"
    assert saved["editorial_verdict"] == "pass"
    assert saved["editorial_cycles"] == 1


def test_revision_required_stays_packaged_with_feedback(tmp_path):
    store = _store(tmp_path)
    opportunity = _packaged_opportunity(store, _MISSING_DISCLOSURE_PACKAGE)
    agent = EditorialReviewAgent(store=store)

    result = agent.run()

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "content_packaged"  # not editorial_passed, not lost
    assert saved["editorial_verdict"] == "revision_required"
    assert saved["editorial_feedback"]["failed_sections"] == ["ctas"]
    assert saved["editorial_cycles"] == 1


def test_badly_broken_package_rejected_immediately(tmp_path):
    store = _store(tmp_path)
    opportunity = _packaged_opportunity(store, _BADLY_BROKEN_PACKAGE)
    agent = EditorialReviewAgent(store=store)

    result = agent.run()

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "lost"
    assert saved["editorial_verdict"] == "reject"
    assert saved["editorial_cycles"] == 1  # rejected on the very first cycle, no revision attempted


def test_revision_required_becomes_reject_after_two_cycles(tmp_path):
    store = _store(tmp_path)
    # Pre-set to simulate a second consecutive revision_required verdict
    opportunity = _packaged_opportunity(store, _MISSING_DISCLOSURE_PACKAGE, editorial_cycles=1)
    agent = EditorialReviewAgent(store=store)

    result = agent.run()

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["stage"] == "lost"
    assert saved["editorial_verdict"] == "reject"
    assert saved["editorial_cycles"] == 2


def test_already_reviewed_opportunity_is_not_re_evaluated(tmp_path):
    store = _store(tmp_path)
    opportunity = _packaged_opportunity(store, _GOOD_PACKAGE, editorial_verdict="pass", stage="editorial_passed")
    agent = EditorialReviewAgent(store=store)

    result = agent.run()

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["editorial_cycles"] == 0  # untouched — already has a verdict


def test_mismatched_category_task_is_a_safe_no_op(tmp_path):
    store = _store(tmp_path)
    opportunity = _packaged_opportunity(store, _MISSING_DISCLOSURE_PACKAGE)
    agent = EditorialReviewAgent(store=store)

    unrelated = Task(goal_id="goal-a", description="unrelated", category="general")
    result = agent.run(task=unrelated)

    saved = next(o for o in result["opportunities"] if o["id"] == opportunity.id)
    assert saved["editorial_verdict"] == ""  # unchanged


def test_report_does_not_mutate_state(tmp_path):
    store = _store(tmp_path)
    _packaged_opportunity(store, _GOOD_PACKAGE)
    agent = EditorialReviewAgent(store=store)
    agent.run()

    before = agent.report()
    after = agent.report()

    assert before == after
