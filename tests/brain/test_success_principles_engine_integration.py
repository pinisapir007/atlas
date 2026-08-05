"""Integration tests for ATLAS Success Principles Engine V1 — exercise
the full real pipeline (KnowledgeBase, CampaignRegistry, BrainMemory,
KPIRegistry, cashflow.profit()) together across multiple laws and
multiple campaigns, the same class of test test_intelligence_engine_
end_to_end.py already established for a different engine one layer
over. Every store is still isolated (_FakeStore-backed) so nothing
here ever touches this project's real .atlas/ state."""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, SuccessLaw
from atlas.brain.success_principles_engine import CLOSING_QUESTION, analyze_success_principles
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _deps():
    memory = BrainMemory(store=_FakeStore())
    return {
        "knowledge": KnowledgeBase(store=_FakeStore()),
        "campaigns": CampaignRegistry(store=_FakeStore()),
        "memory": memory,
        "kpis": KPIRegistry(memory),
    }


def _campaign_with_profit(deps, *, business_objective: str, category: str, law_id: str, revenue: float, cost: float) -> Campaign:
    goal = Goal(description=business_objective)
    deps["memory"].save_goal(goal)
    deps["kpis"].record(f"revenue_{goal.id}", revenue)
    deps["kpis"].record(f"cost_{goal.id}", cost)
    campaign = Campaign(business_objective=business_objective, category=category, goal_id=goal.id, success_law_ids=[law_id])
    deps["campaigns"].save_campaign(campaign)
    return campaign


def test_end_to_end_multiple_laws_multiple_campaigns_across_categories():
    deps = _deps()

    # Law A: a real, evidence-backed principle with a strong real track
    # record (2 of 2 real campaigns profitable).
    finding_a = Finding(source="research", category="affiliate", description="observed pattern", evidence="https://example.com/a", subject="testimonial framing")
    deps["knowledge"].save_finding(finding_a)
    law_a = SuccessLaw(
        principle="first-person testimonial framing outperforms feature-listing for consumer health products",
        source_description="observed across several real competitor funnels",
        evidence_finding_ids=[finding_a.id],
        applicable_business_models=["affiliate"],
    )
    deps["knowledge"].save_success_law(law_a)
    _campaign_with_profit(deps, business_objective="KetoDNA US launch", category="affiliate", law_id=law_a.id, revenue=1000.0, cost=200.0)
    _campaign_with_profit(deps, business_objective="KetoDNA UK launch", category="affiliate", law_id=law_a.id, revenue=800.0, cost=300.0)

    # Law B: a real principle with a weaker, mixed real track record.
    law_b = SuccessLaw(
        principle="scarcity-based CTAs increase conversion for impulse-purchase digital products",
        source_description="observed on a real digital product funnel",
        applicable_business_models=["digital_product"],
    )
    deps["knowledge"].save_success_law(law_b)
    _campaign_with_profit(deps, business_objective="Widget promo 1", category="digital_product", law_id=law_b.id, revenue=100.0, cost=90.0)
    _campaign_with_profit(deps, business_objective="Widget promo 2", category="digital_product", law_id=law_b.id, revenue=50.0, cost=200.0)
    _campaign_with_profit(deps, business_objective="Widget promo 3", category="digital_product", law_id=law_b.id, revenue=40.0, cost=150.0)

    # Law C: recorded, but with no real campaign ever measured against it yet.
    law_c = SuccessLaw(principle="a completely untested, real principle", source_description="observed but never yet applied by ATLAS")
    deps["knowledge"].save_success_law(law_c)

    report = analyze_success_principles(**deps)

    assert len(report.principles) == 3
    assert report.closing_question == CLOSING_QUESTION

    by_id = {p.source_success_law_id: p for p in report.principles}
    principle_a = by_id[law_a.id]
    principle_b = by_id[law_b.id]
    principle_c = by_id[law_c.id]

    assert principle_a.successful_case_count == 2
    assert principle_a.failed_case_count == 0
    assert principle_a.confidence_level == 1.0
    assert principle_a.supporting_evidence == ["https://example.com/a"]

    assert principle_b.successful_case_count == 1
    assert principle_b.failed_case_count == 2
    assert principle_b.confidence_level == 1 / 3

    assert principle_c.confidence_level is None
    assert principle_c.successful_case_count == 0
    assert principle_c.failed_case_count == 0

    # Question 7 -- ranked by real probability of success, highest first;
    # the entirely untested principle sorts last, never fabricated a rank.
    assert [p.source_success_law_id for p in report.principles] == [law_a.id, law_b.id, law_c.id]


def test_ranking_prefers_higher_measured_success_rate_over_raw_case_volume():
    deps = _deps()

    law_high_rate = SuccessLaw(principle="high real success rate, few cases", source_description="real")
    deps["knowledge"].save_success_law(law_high_rate)
    _campaign_with_profit(deps, business_objective="single win", category="affiliate", law_id=law_high_rate.id, revenue=500.0, cost=1.0)

    law_high_volume = SuccessLaw(principle="lower real success rate, more cases", source_description="real")
    deps["knowledge"].save_success_law(law_high_volume)
    for i in range(4):
        _campaign_with_profit(deps, business_objective=f"win {i}", category="affiliate", law_id=law_high_volume.id, revenue=10.0, cost=1.0)
    _campaign_with_profit(deps, business_objective="the one loss", category="affiliate", law_id=law_high_volume.id, revenue=1.0, cost=100.0)

    report = analyze_success_principles(**deps)

    assert report.principles[0].source_success_law_id == law_high_rate.id  # 1/1 = 100% beats 4/5 = 80%
    assert report.principles[0].confidence_level == 1.0
    assert report.principles[1].confidence_level == 0.8


def test_ranking_breaks_ties_among_unmeasured_principles_by_real_evidence_volume():
    deps = _deps()

    finding_1 = Finding(source="research", category="affiliate", description="one citation", evidence="https://example.com/1")
    finding_2 = Finding(source="research", category="affiliate", description="two citations", evidence="https://example.com/2")
    finding_3 = Finding(source="research", category="affiliate", description="two citations", evidence="https://example.com/3")
    for f in (finding_1, finding_2, finding_3):
        deps["knowledge"].save_finding(f)

    law_one_citation = SuccessLaw(principle="weaker evidence, no measured cases", source_description="real", evidence_finding_ids=[finding_1.id])
    law_two_citations = SuccessLaw(principle="stronger evidence, no measured cases", source_description="real", evidence_finding_ids=[finding_2.id, finding_3.id])
    deps["knowledge"].save_success_law(law_one_citation)
    deps["knowledge"].save_success_law(law_two_citations)

    report = analyze_success_principles(**deps)

    # Both have confidence_level=None (zero real measured cases) -- the
    # deterministic tiebreak is real cited evidence volume, not
    # insertion order.
    assert [p.source_success_law_id for p in report.principles] == [law_two_citations.id, law_one_citation.id]


def test_a_realistic_affiliate_marketing_scenario_matching_the_campaign_success_law_association():
    # Mirrors the real shape campaign_advance.py produces in production:
    # a Campaign created with success_law_ids set from
    # opportunity_ranking.relevant_success_laws() at creation time, then
    # real revenue/cost recorded later against its real goal via
    # kpi_intake's founder-reported path. This test builds that same
    # real shape directly (not by calling campaign_advance.py, which
    # needs a live Decision Engine verdict) to prove the engine
    # correctly reasons over data produced the same way the real
    # pipeline produces it.
    deps = _deps()

    finding = Finding(source="research", category="affiliate", description="Keto affiliate offers convert well with real testimonials", evidence="https://example.com/keto-research", subject="KetoDNA", market="US")
    deps["knowledge"].save_finding(finding)
    law = SuccessLaw(
        principle="authentic before/after testimonial content converts better than generic feature-listing for health-niche affiliate offers",
        source_description="observed pattern across several real, independent affiliate case studies",
        evidence_finding_ids=[finding.id],
        applicable_business_models=["affiliate"],
    )
    deps["knowledge"].save_success_law(law)

    campaign = _campaign_with_profit(
        deps,
        business_objective="Become the best Affiliate Marketing business",
        category="affiliate",
        law_id=law.id,
        revenue=750.0,
        cost=150.0,
    )

    report = analyze_success_principles(**deps)

    assert len(report.principles) == 1
    p = report.principles[0]
    assert p.principle == law.principle
    assert p.recommended_implementation == law.principle
    assert p.confidence_level == 1.0
    assert any(campaign.id in c for c in p.conditions_for_success)
    assert any("category 'affiliate'" in c for c in p.conditions_for_success)
    assert p.supporting_evidence == ["https://example.com/keto-research"]
    assert CLOSING_QUESTION in p.possible_improvements
    assert report.closing_question == CLOSING_QUESTION


def test_report_is_recomputed_fresh_and_reflects_a_newly_recorded_outcome():
    # "Nothing is permanently true" -- calling the engine again after a
    # new real outcome is recorded must reflect it immediately, with no
    # caching to go stale (the same discipline decide() itself relies
    # on).
    deps = _deps()
    law = SuccessLaw(principle="a real principle", source_description="real")
    deps["knowledge"].save_success_law(law)

    first = analyze_success_principles(**deps)
    assert first.principles[0].confidence_level is None

    _campaign_with_profit(deps, business_objective="new real campaign", category="affiliate", law_id=law.id, revenue=500.0, cost=1.0)

    second = analyze_success_principles(**deps)
    assert second.principles[0].confidence_level == 1.0
