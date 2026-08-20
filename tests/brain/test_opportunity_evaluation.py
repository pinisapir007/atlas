from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, Opportunity
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.opportunity_evaluation import evaluate_opportunities, evaluate_opportunity


def _kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path / "knowledge.json")


def _store(tmp_path) -> OpportunityStore:
    return OpportunityStore(tmp_path / "opportunities.json")


def _seed_findings(knowledge: KnowledgeBase, category: str, subject: str, count: int) -> list[str]:
    ids = []
    for i in range(count):
        f = Finding(source="research", category=category, subject=subject, description=f"s{i}", evidence=f"https://e/{subject}-{i}", evidence_role="direct_assertion")
        knowledge.save_finding(f)
        ids.append(f.id)
    return ids


def _opp(category: str, subject: str, evidence_ids: list[str], competition: float | None = None) -> Opportunity:
    return Opportunity(subject=subject, description="d", category=category, evidence_finding_ids=evidence_ids, competition=competition)


def test_below_evidence_bar_is_classified_wait(tmp_path):
    knowledge = _kb(tmp_path)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 1)  # below MIN_INDEPENDENT_SOURCES (2)
    opp = _opp("digital_product", "Notion templates", ids)

    result = evaluate_opportunity(opp, knowledge)

    assert result["classification"] == "wait"


def test_crossing_evidence_bar_is_classified_ready(tmp_path):
    knowledge = _kb(tmp_path)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)  # meets MIN_INDEPENDENT_SOURCES
    opp = _opp("digital_product", "Notion templates", ids)

    result = evaluate_opportunity(opp, knowledge)

    assert result["classification"] == "ready"


def test_a_real_second_source_flips_wait_to_ready(tmp_path):
    knowledge = _kb(tmp_path)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 1)
    opp = _opp("digital_product", "Notion templates", ids)
    assert evaluate_opportunity(opp, knowledge)["classification"] == "wait"

    ids += _seed_findings(knowledge, "digital_product", "Notion templates", 1)
    opp = _opp("digital_product", "Notion templates", ids)

    assert evaluate_opportunity(opp, knowledge)["classification"] == "ready"


def test_never_fabricates_unavailable_factors(tmp_path):
    knowledge = _kb(tmp_path)
    ids = _seed_findings(knowledge, "youtube", "Some Channel", 2)  # no real execution channel exists for youtube
    opp = _opp("youtube", "Some Channel", ids, competition=None)

    result = evaluate_opportunity(opp, knowledge)

    assert result["factors"]["competition"] is None
    assert "competition" in result["unknown"]
    assert "market_demand" in result["unknown"]
    assert "affiliate_program_exists" in result["unknown"]
    assert "audience_reach" in result["unknown"]
    assert "revenue_potential_dollars" in result["unknown"]
    assert result["factors"]["execution_readiness"] == 0.0
    assert any("no real execution channel exists yet" in r for r in result["risks"])


def test_never_mutates_the_real_opportunity(tmp_path):
    knowledge = _kb(tmp_path)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)
    opp = _opp("digital_product", "Notion templates", ids)
    stage_before = opp.stage
    competition_before = opp.competition

    evaluate_opportunity(opp, knowledge)

    assert opp.stage == stage_before
    assert opp.competition == competition_before
    assert opp.history == []


def test_ranks_ready_candidates_by_real_evidence_and_execution_readiness(tmp_path):
    knowledge = _kb(tmp_path)
    strong_ids = _seed_findings(knowledge, "digital_product", "Notion templates", 4)  # real channel exists for digital_product
    weak_ids = _seed_findings(knowledge, "digital_product", "Canva templates", 2)
    strong = _opp("digital_product", "Notion templates", strong_ids)
    weak = _opp("digital_product", "Canva templates", weak_ids)
    store = _store(tmp_path)
    store.save_opportunity(strong)
    store.save_opportunity(weak)

    result = evaluate_opportunities("digital_product", store, knowledge)

    assert [c["subject"] for c in result["ready"]] == ["Notion templates", "Canva templates"]
    assert result["wait"] == []


def test_swapping_real_evidence_flips_the_ranking(tmp_path):
    # The Design doc's own falsification test: swap which candidate has
    # more real evidence, the ranking must flip accordingly.
    knowledge = _kb(tmp_path)
    a_ids = _seed_findings(knowledge, "digital_product", "A", 2)
    b_ids = _seed_findings(knowledge, "digital_product", "B", 4)
    store = _store(tmp_path)
    store.save_opportunity(_opp("digital_product", "A", a_ids))
    store.save_opportunity(_opp("digital_product", "B", b_ids))

    result = evaluate_opportunities("digital_product", store, knowledge)
    assert result["ready"][0]["subject"] == "B"  # more real evidence wins


def test_wait_candidates_are_never_ranked_against_ready_ones(tmp_path):
    knowledge = _kb(tmp_path)
    ready_ids = _seed_findings(knowledge, "digital_product", "Ready One", 3)
    wait_ids = _seed_findings(knowledge, "digital_product", "Wait One", 1)
    store = _store(tmp_path)
    store.save_opportunity(_opp("digital_product", "Ready One", ready_ids))
    store.save_opportunity(_opp("digital_product", "Wait One", wait_ids))

    result = evaluate_opportunities("digital_product", store, knowledge)

    assert [c["subject"] for c in result["ready"]] == ["Ready One"]
    assert [c["subject"] for c in result["wait"]] == ["Wait One"]


def test_empty_category_returns_empty_lists_honestly(tmp_path):
    knowledge = _kb(tmp_path)
    store = _store(tmp_path)

    result = evaluate_opportunities("nonexistent_category", store, knowledge)

    assert result == {"ready": [], "wait": []}
