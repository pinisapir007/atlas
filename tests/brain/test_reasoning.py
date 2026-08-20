import pytest

from atlas.brain.models import Opportunity
from atlas.brain.reasoning import IncomparableOpportunitiesError, compare_opportunities


def _opp(subject: str, category: str, stage: str = "ranked", competition: float | None = None, evidence_count: int = 0) -> Opportunity:
    return Opportunity(
        subject=subject,
        description="d",
        category=category,
        stage=stage,
        competition=competition,
        evidence_finding_ids=[f"finding-{i}" for i in range(evidence_count)],
    )


def test_requires_at_least_two_opportunities():
    with pytest.raises(IncomparableOpportunitiesError, match="at least 2"):
        compare_opportunities([_opp("a", "affiliate")])


def test_rejects_comparing_across_different_stages():
    a = _opp("a", "affiliate", stage="ranked")
    b = _opp("b", "affiliate", stage="discovered")
    with pytest.raises(IncomparableOpportunitiesError, match="different real stages"):
        compare_opportunities([a, b])


def test_prefers_more_evidence_when_competition_is_equal():
    strong = _opp("strong", "affiliate", competition=0.3, evidence_count=3)
    weak = _opp("weak", "affiliate", competition=0.3, evidence_count=1)

    result = compare_opportunities([strong, weak])

    assert result["preferred_id"] == strong.id
    assert strong.id in result["reasoning"]


def test_prefers_less_competition_when_evidence_is_equal():
    low_competition = _opp("low", "affiliate", competition=0.1, evidence_count=2)
    high_competition = _opp("high", "affiliate", competition=0.9, evidence_count=2)

    result = compare_opportunities([low_competition, high_competition])

    assert result["preferred_id"] == low_competition.id


def test_never_mutates_the_real_opportunities(tmp_path):
    a = _opp("a", "affiliate", competition=0.3, evidence_count=2)
    b = _opp("b", "affiliate", competition=0.7, evidence_count=1)
    a_stage_before, b_stage_before = a.stage, b.stage

    compare_opportunities([a, b])

    assert a.stage == a_stage_before
    assert b.stage == b_stage_before
    assert a.history == []
    assert b.history == []


def test_missing_competition_is_excluded_not_fabricated_as_zero():
    # competition=None must never silently become "0.0 competition" (the
    # most charitable possible value) -- weighted_average_of_available()
    # excludes it, same fail-closed discipline confidence_score() already
    # establishes for a missing factor.
    unmeasured = _opp("unmeasured", "affiliate", competition=None, evidence_count=3)
    measured_high_competition = _opp("measured", "affiliate", competition=0.9, evidence_count=3)

    result = compare_opportunities([unmeasured, measured_high_competition])

    assert result["scores"][unmeasured.id]["competition_component"] is None
    # with competition excluded, the unmeasured one is judged on evidence
    # alone (equal to the other's evidence) -- it must not be penalized
    # for a real fact it simply doesn't have yet
    assert result["scores"][unmeasured.id]["combined_score"] == 1.0


class TestQualificationRun3FalsificationTest:
    """The real Qualification Run #3 falsification test named in
    docs/DESIGN_EXECUTIVE_REASONING_MVP.md, section 8, kept as a
    permanent, automated regression -- not just a one-time manual run.
    Swapping which real Opportunity has more evidence/less competition
    must flip the stated preference, or the capability isn't real."""

    def test_preference_flips_when_the_real_evidence_is_swapped(self):
        first = _opp("Keto Diet Guide", "affiliate", competition=0.4, evidence_count=3)
        second = _opp("Project Management SaaS", "saas", competition=0.4, evidence_count=1)

        before = compare_opportunities([first, second])
        assert before["preferred_id"] == first.id

        # swap: now `second` has the stronger real evidence
        first.evidence_finding_ids = [f"finding-{i}" for i in range(1)]
        second.evidence_finding_ids = [f"finding-{i}" for i in range(3)]

        after = compare_opportunities([first, second])
        assert after["preferred_id"] == second.id

    def test_preference_flips_when_the_real_competition_is_swapped(self):
        first = _opp("a", "affiliate", competition=0.2, evidence_count=2)
        second = _opp("b", "saas", competition=0.8, evidence_count=2)

        before = compare_opportunities([first, second])
        assert before["preferred_id"] == first.id

        first.competition, second.competition = second.competition, first.competition

        after = compare_opportunities([first, second])
        assert after["preferred_id"] == second.id
