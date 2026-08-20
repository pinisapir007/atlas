from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, SuccessLaw
from atlas.brain.opportunity_ranking import (
    cited_evidence,
    explain_opportunity_subject,
    opportunity_confidence,
    rank_opportunities,
    relevant_success_laws,
)


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def test_opportunity_confidence_is_none_with_no_subject_scoped_evidence(tmp_path):
    kb = _kb(tmp_path)

    result = opportunity_confidence("affiliate", "KetoDNA", kb)

    assert result["score"] is None
    assert result["factors_available"] == 0
    assert result["independent_sources"] == 0
    assert result["recommended_market"] == ""


def test_opportunity_confidence_combines_available_factors(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="rising demand", evidence="https://x/1", subject="KetoDNA")
    )

    result = opportunity_confidence("affiliate", "KetoDNA", kb)

    assert result["score"] is not None
    assert result["factors_available"] == 2  # source_corroboration + recency
    assert result["independent_sources"] == 1
    assert result["subject"] == "KetoDNA"


def test_opportunity_confidence_ignores_a_different_subjects_evidence(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="x", evidence="https://x/1", subject="BudgetWise")
    )

    result = opportunity_confidence("affiliate", "KetoDNA", kb)

    assert result["score"] is None
    assert result["independent_sources"] == 0


def test_opportunity_confidence_ignores_category_general_findings_with_no_subject(tmp_path):
    # A category-general finding ("affiliate marketing pays well") isn't
    # evidence FOR a specific opportunity -- mixing it in would blur the
    # exact distinction opportunity-level scoping exists to make.
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="general fact", evidence="https://x/1"))

    result = opportunity_confidence("affiliate", "KetoDNA", kb)

    assert result["score"] is None


def test_recommended_market_is_the_most_common_real_market_among_evidence(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA", market="US")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="KetoDNA", market="US")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="c", evidence="https://x/3", subject="KetoDNA", market="DE")
    )

    result = opportunity_confidence("affiliate", "KetoDNA", kb)

    assert result["recommended_market"] == "US"


def test_rank_opportunities_returns_nothing_when_no_finding_names_a_subject(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="general fact", evidence="https://x/1"))

    assert rank_opportunities("affiliate", kb) == []


def test_rank_opportunities_orders_by_confidence_descending(tmp_path):
    kb = _kb(tmp_path)
    # "Strong" has two independent sources; "Weak" has one.
    kb.save_finding(
        Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="Strong", evidence_role="direct_assertion")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="Strong", evidence_role="direct_assertion")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="c", evidence="https://x/3", subject="Weak", evidence_role="direct_assertion")
    )

    ranked = rank_opportunities("affiliate", kb)

    assert [r["subject"] for r in ranked] == ["Strong", "Weak"]


def test_rank_opportunities_ignores_other_categories(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="youtube", description="a", evidence="https://x/1", subject="SomeChannel")
    )

    assert rank_opportunities("affiliate", kb) == []


# --- explain_opportunity_subject -----------------------------------------


def test_explain_cites_real_evidence_and_recommended_market(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="rising demand", evidence="https://x/1", subject="KetoDNA", market="US")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="forum buzz", evidence="https://x/2", subject="KetoDNA", market="US")
    )

    explanation = explain_opportunity_subject("affiliate", "KetoDNA", kb, rank=1)

    assert len(explanation["evidence"]) == 2
    assert {e["description"] for e in explanation["evidence"]} == {"rising demand", "forum buzz"}
    assert explanation["recommended_market"] == "US"
    assert "ranked #1" in explanation["rank_reason"]


def test_explain_names_the_below_threshold_risk_with_one_source(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA")
    )

    explanation = explain_opportunity_subject("affiliate", "KetoDNA", kb)

    assert any("below the standing 2-source policy bar" in r for r in explanation["risks"])


def test_explain_names_the_no_market_risk_when_evidence_is_market_general(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA")
    )
    kb.save_finding(
        Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="KetoDNA")
    )

    explanation = explain_opportunity_subject("affiliate", "KetoDNA", kb)

    assert any("no evidence names a specific market" in r for r in explanation["risks"])
    assert not any("below the standing 2-source" in r for r in explanation["risks"])


def test_explain_never_fabricates_roi_or_probability_fields(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA")
    )

    explanation = explain_opportunity_subject("affiliate", "KetoDNA", kb)

    assert "expected_roi" not in explanation
    assert "probability_of_success" not in explanation
    assert any("no real revenue/cost is attributed per-opportunity yet" in r for r in explanation["risks"])


# --- cited_evidence ---------------------------------------------------


def test_cited_evidence_returns_real_urls(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA"))
    kb.save_finding(Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="KetoDNA"))

    assert set(cited_evidence("affiliate", "KetoDNA", kb)) == {"https://x/1", "https://x/2"}


def test_cited_evidence_is_empty_when_nothing_is_tagged(tmp_path):
    kb = _kb(tmp_path)

    assert cited_evidence("affiliate", "KetoDNA", kb) == []


# --- relevant_success_laws ----------------------------------------------


def test_relevant_success_laws_is_empty_when_none_recorded(tmp_path):
    kb = _kb(tmp_path)

    assert relevant_success_laws("affiliate", kb) == []


def test_relevant_success_laws_includes_a_matching_business_model(tmp_path):
    kb = _kb(tmp_path)
    law = SuccessLaw(principle="p", source_description="s", applicable_business_models=["affiliate", "digital_product"])
    kb.save_success_law(law)

    laws = relevant_success_laws("affiliate", kb)

    assert [l.id for l in laws] == [law.id]


def test_relevant_success_laws_excludes_a_non_matching_business_model(tmp_path):
    kb = _kb(tmp_path)
    kb.save_success_law(SuccessLaw(principle="p", source_description="s", applicable_business_models=["content"]))

    assert relevant_success_laws("affiliate", kb) == []


def test_relevant_success_laws_includes_a_category_general_law(tmp_path):
    kb = _kb(tmp_path)
    law = SuccessLaw(principle="p", source_description="s", applicable_business_models=[])
    kb.save_success_law(law)

    laws = relevant_success_laws("affiliate", kb)

    assert [l.id for l in laws] == [law.id]


def test_relevant_success_laws_ranks_evidence_backed_above_hypothesis(tmp_path):
    kb = _kb(tmp_path)
    finding = Finding(source="research", category="affiliate", description="x", evidence="https://x/1")
    kb.save_finding(finding)
    hypothesis = SuccessLaw(principle="hypothesis", source_description="s", applicable_business_models=["affiliate"])
    backed = SuccessLaw(
        principle="backed", source_description="s", applicable_business_models=["affiliate"], evidence_finding_ids=[finding.id]
    )
    kb.save_success_law(hypothesis)
    kb.save_success_law(backed)

    laws = relevant_success_laws("affiliate", kb)

    assert [l.principle for l in laws] == ["backed", "hypothesis"]


def test_relevant_success_laws_ranks_more_evidence_higher(tmp_path):
    kb = _kb(tmp_path)
    f1 = Finding(source="research", category="affiliate", description="a", evidence="https://x/1")
    f2 = Finding(source="research", category="affiliate", description="b", evidence="https://x/2")
    kb.save_finding(f1)
    kb.save_finding(f2)
    thin = SuccessLaw(principle="thin", source_description="s", applicable_business_models=["affiliate"], evidence_finding_ids=[f1.id])
    thick = SuccessLaw(
        principle="thick", source_description="s", applicable_business_models=["affiliate"], evidence_finding_ids=[f1.id, f2.id]
    )
    kb.save_success_law(thin)
    kb.save_success_law(thick)

    laws = relevant_success_laws("affiliate", kb)

    assert [l.principle for l in laws] == ["thick", "thin"]


def test_explain_opportunity_subject_surfaces_relevant_success_laws(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA"))
    law = SuccessLaw(principle="p", source_description="s", applicable_business_models=["affiliate"])
    kb.save_success_law(law)

    explanation = explain_opportunity_subject("affiliate", "KetoDNA", kb)

    assert [l.id for l in explanation["success_laws"]] == [law.id]
