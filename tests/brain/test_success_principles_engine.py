import dataclasses

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, SuccessLaw
from atlas.brain.success_principles_engine import (
    CLOSING_QUESTION,
    SuccessPrinciple,
    analyze_success_principles,
)
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


def _record_profit(deps, goal: Goal, revenue: float, cost: float):
    deps["memory"].save_goal(goal)
    deps["kpis"].record(f"revenue_{goal.id}", revenue)
    deps["kpis"].record(f"cost_{goal.id}", cost)


def test_zero_laws_returns_no_principles_but_still_asks_the_closing_question():
    deps = _deps()
    report = analyze_success_principles(**deps)
    assert report.principles == []
    assert report.closing_question == CLOSING_QUESTION == "What can ATLAS do better than the current best?"


def test_a_law_with_no_linked_campaigns_has_all_honest_gaps_named():
    deps = _deps()
    law = SuccessLaw(principle="a real, transferable principle", source_description="observed somewhere real")
    deps["knowledge"].save_success_law(law)

    report = analyze_success_principles(**deps)

    assert len(report.principles) == 1
    p = report.principles[0]
    assert p.confidence_level is None
    assert p.successful_case_count == 0
    assert p.failed_case_count == 0
    assert p.conditions_for_success == []
    assert p.conditions_for_failure == []
    assert "unevidenced hypothesis" in " ".join(p.known_limitations)
    assert "untested in real execution" in " ".join(p.known_limitations)


def test_a_law_with_real_evidence_is_not_flagged_as_an_unevidenced_hypothesis():
    deps = _deps()
    finding = Finding(source="research", category="affiliate", description="real", evidence="https://example.com/real-evidence")
    deps["knowledge"].save_finding(finding)
    law = SuccessLaw(principle="a real, transferable principle", source_description="observed somewhere real", evidence_finding_ids=[finding.id])
    deps["knowledge"].save_success_law(law)

    report = analyze_success_principles(**deps)

    p = report.principles[0]
    assert p.supporting_evidence == ["https://example.com/real-evidence"]
    assert not any("unevidenced hypothesis" in m for m in p.known_limitations)


def test_a_success_and_a_failure_case_produce_correct_classification_and_confidence():
    deps = _deps()
    law = SuccessLaw(principle="first-person framing beats feature lists", source_description="real")
    deps["knowledge"].save_success_law(law)

    success_goal = Goal(description="affiliate goal 1")
    _record_profit(deps, success_goal, revenue=500.0, cost=100.0)  # +400 profit
    success_campaign = Campaign(business_objective="sell KetoDNA", category="affiliate", goal_id=success_goal.id, success_law_ids=[law.id])
    deps["campaigns"].save_campaign(success_campaign)

    fail_goal = Goal(description="affiliate goal 2")
    _record_profit(deps, fail_goal, revenue=50.0, cost=200.0)  # -150 profit
    fail_campaign = Campaign(business_objective="sell WidgetX", category="affiliate", goal_id=fail_goal.id, success_law_ids=[law.id])
    deps["campaigns"].save_campaign(fail_campaign)

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.successful_case_count == 1
    assert p.failed_case_count == 1
    assert p.confidence_level == 0.5
    assert any(success_campaign.id in c for c in p.conditions_for_success)
    assert any(fail_campaign.id in c for c in p.conditions_for_failure)
    assert any("category 'affiliate'" in c for c in p.conditions_for_success)
    assert any("category 'affiliate'" in c for c in p.conditions_for_failure)


def test_all_successful_cases_yield_full_confidence_and_no_all_failed_warning():
    deps = _deps()
    law = SuccessLaw(principle="a real principle", source_description="real")
    deps["knowledge"].save_success_law(law)
    goal = Goal(description="g")
    _record_profit(deps, goal, revenue=100.0, cost=1.0)
    deps["campaigns"].save_campaign(Campaign(business_objective="x", category="affiliate", goal_id=goal.id, success_law_ids=[law.id]))

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.confidence_level == 1.0
    assert not any("do not treat as validated" in m for m in p.known_limitations)


def test_all_failed_cases_yield_zero_confidence_and_the_all_failed_warning():
    deps = _deps()
    law = SuccessLaw(principle="a real principle", source_description="real")
    deps["knowledge"].save_success_law(law)
    goal = Goal(description="g")
    _record_profit(deps, goal, revenue=1.0, cost=100.0)
    deps["campaigns"].save_campaign(Campaign(business_objective="x", category="affiliate", goal_id=goal.id, success_law_ids=[law.id]))

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.confidence_level == 0.0
    assert any("do not treat as validated" in m for m in p.known_limitations)


def test_a_campaign_with_no_goal_id_is_treated_as_unmeasured_not_failed():
    deps = _deps()
    law = SuccessLaw(principle="a real principle", source_description="real")
    deps["knowledge"].save_success_law(law)
    deps["campaigns"].save_campaign(Campaign(business_objective="x", category="affiliate", success_law_ids=[law.id]))  # no goal_id

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.successful_case_count == 0
    assert p.failed_case_count == 0
    assert p.confidence_level is None
    assert any("1 real campaign(s)" in m for m in p.known_limitations)


def test_a_campaign_whose_goal_id_does_not_resolve_is_treated_as_unmeasured():
    deps = _deps()
    law = SuccessLaw(principle="a real principle", source_description="real")
    deps["knowledge"].save_success_law(law)
    deps["campaigns"].save_campaign(Campaign(business_objective="x", category="affiliate", goal_id="goal-does-not-exist", success_law_ids=[law.id]))

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.confidence_level is None
    assert p.successful_case_count == 0
    assert p.failed_case_count == 0


def test_a_finding_id_that_no_longer_resolves_is_silently_skipped():
    deps = _deps()
    law = SuccessLaw(principle="a real principle", source_description="real", evidence_finding_ids=["finding-does-not-exist"])
    deps["knowledge"].save_success_law(law)

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.supporting_evidence == []
    # a law with a (now-stale) citation id is still recorded as "cited an id",
    # not honestly indistinguishable from never having cited one -- but this
    # engine must not crash, and must not fabricate a URL that no longer
    # exists.


def test_a_finding_with_empty_evidence_is_never_cited():
    deps = _deps()
    finding = Finding(source="research", category="affiliate", description="real but no url", evidence="")
    deps["knowledge"].save_finding(finding)
    law = SuccessLaw(principle="a real principle", source_description="real", evidence_finding_ids=[finding.id])
    deps["knowledge"].save_success_law(law)

    report = analyze_success_principles(**deps)
    assert report.principles[0].supporting_evidence == []


def test_campaigns_linked_to_a_different_law_are_not_counted():
    deps = _deps()
    law_a = SuccessLaw(principle="principle A", source_description="real")
    law_b = SuccessLaw(principle="principle B", source_description="real")
    deps["knowledge"].save_success_law(law_a)
    deps["knowledge"].save_success_law(law_b)

    goal = Goal(description="g")
    _record_profit(deps, goal, revenue=500.0, cost=1.0)
    deps["campaigns"].save_campaign(Campaign(business_objective="x", category="affiliate", goal_id=goal.id, success_law_ids=[law_a.id]))

    report = analyze_success_principles(**deps)
    by_law = {p.source_success_law_id: p for p in report.principles}

    assert by_law[law_a.id].successful_case_count == 1
    assert by_law[law_b.id].successful_case_count == 0
    assert by_law[law_b.id].confidence_level is None


def test_recommended_implementation_is_always_the_laws_own_principle_text_never_the_source_description():
    deps = _deps()
    law = SuccessLaw(principle="the real, transferable rule", source_description="a description of what the external source literally did, never to be copied")
    deps["knowledge"].save_success_law(law)

    report = analyze_success_principles(**deps)
    p = report.principles[0]

    assert p.recommended_implementation == "the real, transferable rule"
    assert "external source literally did" not in p.recommended_implementation


def test_possible_improvements_always_contains_the_exact_closing_question():
    deps = _deps()
    deps["knowledge"].save_success_law(SuccessLaw(principle="p", source_description="real"))

    report = analyze_success_principles(**deps)
    assert CLOSING_QUESTION in report.principles[0].possible_improvements


def test_every_principle_exposes_exactly_the_founders_eight_named_fields_plus_provenance():
    field_names = {f.name for f in dataclasses.fields(SuccessPrinciple)}
    founders_eight = {
        "principle",
        "supporting_evidence",
        "confidence_level",
        "known_limitations",
        "conditions_for_success",
        "conditions_for_failure",
        "recommended_implementation",
        "possible_improvements",
    }
    assert founders_eight.issubset(field_names)


def test_analyze_success_principles_never_writes_a_success_law_finding_or_campaign():
    deps = _deps()
    deps["knowledge"].save_success_law(SuccessLaw(principle="p", source_description="real"))
    laws_before = len(deps["knowledge"].success_laws())
    findings_before = len(deps["knowledge"].findings())
    campaigns_before = len(deps["campaigns"].campaigns())

    analyze_success_principles(**deps)

    assert len(deps["knowledge"].success_laws()) == laws_before
    assert len(deps["knowledge"].findings()) == findings_before
    assert len(deps["campaigns"].campaigns()) == campaigns_before
