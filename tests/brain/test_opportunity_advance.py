from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim, Finding, Opportunity
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.opportunity_advance import advance_opportunities_from_findings


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _store(tmp_path):
    return OpportunityStore(tmp_path / "opportunities.json")


def _sourced(category: str, subject: str, i: int) -> Finding:
    # evidence_role="direct_assertion" (2026-08-17, ONE BRAIN Evidence Role
    # Gate): this shared scaffolding helper isn't testing role/independence
    # semantics itself (see test_j/test_k below for those dedicated tests)
    # -- it just needs N genuinely real, trustworthy, independent sources
    # to exercise Bridge 1's own find-or-create/accumulate logic, the same
    # way it always has.
    return Finding(
        source="research", category=category, description=f"real signal {i} about {subject}",
        evidence=f"https://example.com/{subject}/{i}", subject=subject, evidence_role="direct_assertion",
    )


class TestDesignDocFalsificationTest:
    """docs/DESIGN_BRIDGE_1_FINDING_TO_OPPORTUNITY.md's own 3-part
    falsification test, kept as a permanent automated regression."""

    def test_part_1_two_real_findings_create_exactly_one_opportunity(self, tmp_path):
        kb = _kb(tmp_path)
        store = _store(tmp_path)
        kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 1))
        kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 2))

        created = advance_opportunities_from_findings(kb, store)

        assert len(created) == 1
        all_opportunities = store.opportunities()
        assert len(all_opportunities) == 1
        opp = all_opportunities[0]
        assert opp.subject == "Keto Diet Guide"
        assert opp.category == "affiliate"
        assert sorted(opp.evidence_finding_ids) == sorted(f.id for f in kb.findings())

    def test_part_2_a_third_finding_updates_the_same_opportunity_not_a_duplicate(self, tmp_path):
        kb = _kb(tmp_path)
        store = _store(tmp_path)
        kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 1))
        kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 2))
        [first_pass] = advance_opportunities_from_findings(kb, store)
        original_id = first_pass.id

        kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 3))
        changed = advance_opportunities_from_findings(kb, store)

        assert len(changed) == 1
        assert changed[0].id == original_id  # same Opportunity, not a duplicate
        all_opportunities = store.opportunities()
        assert len(all_opportunities) == 1
        assert len(all_opportunities[0].evidence_finding_ids) == 3

    def test_part_3_a_single_finding_below_the_bar_creates_nothing(self, tmp_path):
        kb = _kb(tmp_path)
        store = _store(tmp_path)
        assert MIN_INDEPENDENT_SOURCES >= 2  # sanity: this test is only meaningful if the real bar is >= 2
        kb.save_finding(_sourced("saas", "Project Management SaaS", 1))

        created = advance_opportunities_from_findings(kb, store)

        assert created == []
        assert store.opportunities() == []


def test_findings_without_a_real_subject_are_never_grouped_into_an_opportunity(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="d", evidence="https://x.com/1", subject=""))
    kb.save_finding(Finding(source="research", category="affiliate", description="d", evidence="https://x.com/2", subject=""))

    created = advance_opportunities_from_findings(kb, store)

    assert created == []
    assert store.opportunities() == []


def test_findings_without_real_evidence_are_never_counted(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="d", evidence="", subject="Keto Diet Guide"))
    kb.save_finding(Finding(source="research", category="affiliate", description="d", evidence="", subject="Keto Diet Guide"))

    created = advance_opportunities_from_findings(kb, store)

    assert created == []


def test_a_second_call_with_no_new_evidence_is_a_real_noop(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 1))
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 2))
    advance_opportunities_from_findings(kb, store)

    second_call = advance_opportunities_from_findings(kb, store)

    assert second_call == []


def test_never_advances_stage_past_discovered(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 1))
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 2))

    [created] = advance_opportunities_from_findings(kb, store)

    assert created.stage == "discovered"
    assert created.history == []  # transition() never called


def test_never_sets_score_or_competition(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 1))
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 2))

    [created] = advance_opportunities_from_findings(kb, store)

    assert created.score is None
    assert created.competition is None


def test_two_different_subjects_produce_two_separate_opportunities(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 1))
    kb.save_finding(_sourced("affiliate", "Keto Diet Guide", 2))
    kb.save_finding(_sourced("saas", "Project Management SaaS", 1))
    kb.save_finding(_sourced("saas", "Project Management SaaS", 2))

    created = advance_opportunities_from_findings(kb, store)

    assert len(created) == 2
    assert {o.subject for o in created} == {"Keto Diet Guide", "Project Management SaaS"}


# --- Entity Convergence, end-to-end through the real Bridge 1 (2026-08-17, ONE BRAIN Root Implementation) ---


def test_d_alias_introduced_after_opportunity_exists_creates_no_duplicate(tmp_path):
    """Test D: the exact real-world scenario the design audit proved
    breaks a purely-computed representative -- run through the real
    Bridge 1 entry point, not just resolve_canonical_subject() alone."""
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(_sourced("affiliate", "prostadine::vendorB", 1))
    kb.save_finding(_sourced("affiliate", "prostadine::vendorB", 2))
    [first] = advance_opportunities_from_findings(kb, store)
    assert first.subject == "prostadine::vendorB"

    # a new, lexicographically-smaller alias is linked after the fact
    link_finding = _sourced("affiliate", "prostadine::vendorB", 3)
    kb.save_finding(link_finding)
    kb.save_claim(Claim(
        subject_id="prostadine::vendorB", predicate="possibly_same_as", object_id="prostadine::vendorA",
        evidence_finding_ids=[link_finding.id],
    ))
    kb.save_finding(_sourced("affiliate", "prostadine::vendorA", 1))
    kb.save_finding(_sourced("affiliate", "prostadine::vendorA", 2))

    advance_opportunities_from_findings(kb, store)

    all_opportunities = store.opportunities()
    assert len(all_opportunities) == 1  # no duplicate created
    assert all_opportunities[0].id == first.id
    assert all_opportunities[0].subject == "prostadine::vendorB"  # pinned anchor unchanged


# --- J/K: Bridge 1 and duplicate-origin evidence (2026-08-17, ONE BRAIN Evidence Provenance) ---


def test_j_bridge_1_does_not_create_opportunity_from_duplicated_origin(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    same_url = "https://example.com/prostadine"
    kb.save_finding(Finding(source="marketplace_catalog", category="affiliate", description="d1", evidence=same_url, subject="Prostadine"))
    kb.save_finding(Finding(source="browser", category="affiliate", description="d2", evidence=same_url + "?utm_source=newsletter", subject="Prostadine"))

    created = advance_opportunities_from_findings(kb, store)

    assert created == []
    assert store.opportunities() == []


def test_k_bridge_1_creates_exactly_one_opportunity_with_two_genuinely_independent_sources(tmp_path):
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    kb.save_finding(Finding(source="marketplace_catalog", category="affiliate", description="d1", evidence="https://vendor.example.com/prostadine", subject="Prostadine", evidence_role="direct_assertion"))
    kb.save_finding(Finding(source="browser", category="affiliate", description="d2", evidence="https://independent-review.example.com/prostadine", subject="Prostadine", evidence_role="direct_assertion"))

    created = advance_opportunities_from_findings(kb, store)

    assert len(created) == 1
    assert store.opportunities()[0].subject == "Prostadine"


def test_e_two_pinned_opportunities_later_linked_are_never_merged_or_tripled(tmp_path):
    """Test E (Bridge-1 half; the warning half is covered in test_console.py)."""
    kb = _kb(tmp_path)
    store = _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))
    link_finding = _sourced("affiliate", "prostadine::vendorA", 1)
    kb.save_finding(link_finding)
    kb.save_claim(Claim(
        subject_id="prostadine::vendorA", predicate="possibly_same_as", object_id="prostadine::vendorB",
        evidence_finding_ids=[link_finding.id],
    ))
    kb.save_finding(_sourced("affiliate", "prostadine::vendorA", 2))
    kb.save_finding(_sourced("affiliate", "prostadine::vendorB", 1))
    kb.save_finding(_sourced("affiliate", "prostadine::vendorB", 2))

    advance_opportunities_from_findings(kb, store)

    all_opportunities = store.opportunities()
    assert len(all_opportunities) == 2  # untouched -- no merge, no third
