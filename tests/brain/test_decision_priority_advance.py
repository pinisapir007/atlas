from atlas.brain.decision_priority_advance import REASONING_PRIORITY_BOOST, apply_reasoning_priority
from atlas.brain.models import Decision, Opportunity, Task


def _decision(category: str, verdict: str = "invest") -> Decision:
    return Decision(category=category, verdict=verdict, confidence=0.9, factors={})


def _task(priority_score: float = 0.0) -> Task:
    return Task(goal_id="g1", description="d", priority_score=priority_score)


def _opp(opp_id_suffix: str, category: str) -> Opportunity:
    o = Opportunity(subject=opp_id_suffix, description="d", category=category)
    return o


def test_boosts_priority_only_for_the_reasoning_preferred_category():
    affiliate_opp = _opp("Keto Diet Guide", "affiliate")
    saas_opp = _opp("Project Management SaaS", "saas")
    opportunities_by_id = {affiliate_opp.id: affiliate_opp, saas_opp.id: saas_opp}
    comparisons = [{"preferred_id": affiliate_opp.id, "compared": [affiliate_opp.id, saas_opp.id]}]

    affiliate_decision, affiliate_task = _decision("affiliate"), _task()
    saas_decision, saas_task = _decision("saas"), _task()

    boosted = apply_reasoning_priority(
        [(affiliate_decision, affiliate_task), (saas_decision, saas_task)], comparisons, opportunities_by_id
    )

    assert boosted == [affiliate_task]
    assert affiliate_task.priority_score == REASONING_PRIORITY_BOOST
    assert saas_task.priority_score == 0.0  # untouched


def test_pairs_with_no_real_task_are_skipped_not_errored():
    opportunities_by_id = {}
    already_invested_decision = _decision("affiliate", verdict="already_invested")

    boosted = apply_reasoning_priority([(already_invested_decision, None)], [], opportunities_by_id)

    assert boosted == []


def test_no_comparisons_means_no_boosts_at_all():
    decision, task = _decision("affiliate"), _task()

    boosted = apply_reasoning_priority([(decision, task)], [], {})

    assert boosted == []
    assert task.priority_score == 0.0


class TestDesignDocFalsificationTest:
    """docs/DESIGN_BRIDGE_3_REASONING_TO_DECISION.md's own falsification
    test, kept as a permanent automated regression."""

    def test_part_1_preferred_category_gets_higher_priority_than_its_sibling(self):
        preferred_opp = _opp("preferred", "affiliate")
        other_opp = _opp("other", "saas")
        opportunities_by_id = {preferred_opp.id: preferred_opp, other_opp.id: other_opp}
        comparisons = [{"preferred_id": preferred_opp.id, "compared": [preferred_opp.id, other_opp.id]}]

        preferred_task, other_task = _task(), _task()
        apply_reasoning_priority(
            [(_decision("affiliate"), preferred_task), (_decision("saas"), other_task)], comparisons, opportunities_by_id
        )

        assert preferred_task.priority_score > other_task.priority_score

    def test_part_2_both_categories_still_get_their_own_real_verdict_untouched(self):
        # structural guarantee: the bridge never sees or modifies verdict at all
        preferred_opp = _opp("preferred", "affiliate")
        opportunities_by_id = {preferred_opp.id: preferred_opp}
        comparisons = [{"preferred_id": preferred_opp.id, "compared": [preferred_opp.id]}]

        affiliate_decision = _decision("affiliate", verdict="insufficient_evidence")
        saas_decision = _decision("saas", verdict="invest")
        affiliate_task, saas_task = _task(), _task()

        apply_reasoning_priority(
            [(affiliate_decision, affiliate_task), (saas_decision, saas_task)], comparisons, opportunities_by_id
        )

        assert affiliate_decision.verdict == "insufficient_evidence"
        assert saas_decision.verdict == "invest"

    def test_part_3_decisive_check_preference_never_overrides_the_real_verdict(self):
        # Reasoning prefers "affiliate", but affiliate's REAL evidence
        # only supports insufficient_evidence while saas's supports
        # invest -- the real verdicts must stay exactly as each
        # category's own evidence dictates, regardless of preference.
        preferred_opp = _opp("weaker-evidence-but-preferred", "affiliate")
        other_opp = _opp("stronger-evidence-not-preferred", "saas")
        opportunities_by_id = {preferred_opp.id: preferred_opp, other_opp.id: other_opp}
        comparisons = [{"preferred_id": preferred_opp.id, "compared": [preferred_opp.id, other_opp.id]}]

        affiliate_decision = _decision("affiliate", verdict="insufficient_evidence")
        saas_decision = _decision("saas", verdict="invest")
        affiliate_task, saas_task = None, _task()  # insufficient_evidence produces no real task

        boosted = apply_reasoning_priority(
            [(affiliate_decision, affiliate_task), (saas_decision, saas_task)], comparisons, opportunities_by_id
        )

        assert affiliate_decision.verdict == "insufficient_evidence"  # unchanged despite being "preferred"
        assert saas_decision.verdict == "invest"  # unchanged despite NOT being preferred
        assert boosted == []  # the preferred category had no real task to boost -- honestly reflected, not faked

    def test_part_4_a_changed_preference_changes_which_task_gets_boosted(self):
        opp_a = _opp("a", "affiliate")
        opp_b = _opp("b", "saas")
        opportunities_by_id = {opp_a.id: opp_a, opp_b.id: opp_b}
        task_a, task_b = _task(), _task()
        decisions_and_tasks = [(_decision("affiliate"), task_a), (_decision("saas"), task_b)]

        apply_reasoning_priority(decisions_and_tasks, [{"preferred_id": opp_a.id, "compared": [opp_a.id, opp_b.id]}], opportunities_by_id)
        assert task_a.priority_score > task_b.priority_score

        task_a2, task_b2 = _task(), _task()
        apply_reasoning_priority(
            [(_decision("affiliate"), task_a2), (_decision("saas"), task_b2)],
            [{"preferred_id": opp_b.id, "compared": [opp_a.id, opp_b.id]}],
            opportunities_by_id,
        )
        assert task_b2.priority_score > task_a2.priority_score
