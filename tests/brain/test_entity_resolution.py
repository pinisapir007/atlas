from atlas.brain.entity_resolution import detect_pinned_identity_conflicts, resolve_canonical_subject
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim, Finding, Opportunity
from atlas.brain.opportunities import OpportunityStore


def _kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path / "knowledge.json")


def _store(tmp_path) -> OpportunityStore:
    return OpportunityStore(tmp_path / "opportunities.json")


def _finding(subject: str) -> Finding:
    return Finding(source="test", category="affiliate", description="d", evidence="https://x.com/1", subject=subject)


def _link(knowledge: KnowledgeBase, a: str, b: str) -> Claim:
    """A real, supported possibly_same_as Claim -- evidence_finding_ids
    must resolve to a real Finding (save_claim()'s own validation)."""
    finding = _finding(a)
    knowledge.save_finding(finding)
    claim = Claim(subject_id=a, predicate="possibly_same_as", object_id=b, evidence_finding_ids=[finding.id])
    knowledge.save_claim(claim)
    return claim


def test_no_aliases_returns_the_subject_unchanged(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    assert resolve_canonical_subject("prostadine::vendorB", "affiliate", kb, store) == "prostadine::vendorB"


def test_alias_before_any_opportunity_uses_lexicographic_representative(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    _link(kb, "prostadine::vendorB", "prostadine::vendorA")

    assert resolve_canonical_subject("prostadine::vendorB", "affiliate", kb, store) == "prostadine::vendorA"
    assert resolve_canonical_subject("prostadine::vendorA", "affiliate", kb, store) == "prostadine::vendorA"


def test_alias_after_opportunity_exists_does_not_change_the_pinned_anchor(tmp_path):
    """The exact counterexample the design audit proved: a new,
    lexicographically-smaller alias must NOT silently move an already-
    pinned Opportunity's identity."""
    kb, store = _kb(tmp_path), _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))

    _link(kb, "prostadine::vendorB", "prostadine::vendorA")  # "vendorA" < "vendorB" lexicographically

    assert resolve_canonical_subject("prostadine::vendorB", "affiliate", kb, store) == "prostadine::vendorB"
    assert resolve_canonical_subject("prostadine::vendorA", "affiliate", kb, store) == "prostadine::vendorB"


def test_contradicted_link_stops_participating_without_rewriting_history(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    claim = _link(kb, "prostadine::vendorB", "prostadine::vendorA")
    assert resolve_canonical_subject("prostadine::vendorA", "affiliate", kb, store) == "prostadine::vendorA"

    contradicting_finding = _finding("prostadine::vendorA")
    kb.save_finding(contradicting_finding)
    claim.contradicted_by_finding_ids = [contradicting_finding.id]
    kb.save_claim(claim)

    # self-healing: the now-contradicted link simply stops contributing,
    # no destructive rewrite of anything already saved
    assert resolve_canonical_subject("prostadine::vendorA", "affiliate", kb, store) == "prostadine::vendorA"
    assert resolve_canonical_subject("prostadine::vendorB", "affiliate", kb, store) == "prostadine::vendorB"


def test_two_existing_pinned_opportunities_fail_closed_no_merge(tmp_path):
    """The genuinely hard case: two REAL, already-persisted Opportunities
    later linked -- must never merge, never pick one, never create a
    third."""
    kb, store = _kb(tmp_path), _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))

    _link(kb, "prostadine::vendorA", "prostadine::vendorB")

    # each resolves to itself -- Bridge 1's existing_by_key lookup will
    # still find each real Opportunity under its own real subject
    assert resolve_canonical_subject("prostadine::vendorA", "affiliate", kb, store) == "prostadine::vendorA"
    assert resolve_canonical_subject("prostadine::vendorB", "affiliate", kb, store) == "prostadine::vendorB"
    assert len(store.opportunities()) == 2  # untouched, no merge, no third


def test_one_alias_linked_to_two_conflicting_pinned_anchors_fails_closed(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))
    _link(kb, "prostadine::vendorA", "prostadine::vendorC")
    _link(kb, "prostadine::vendorB", "prostadine::vendorC")

    assert resolve_canonical_subject("prostadine::vendorC", "affiliate", kb, store) == "prostadine::vendorC"


def test_restart_new_store_instances_still_resolve_the_pinned_anchor_correctly(tmp_path):
    path_kb = tmp_path / "knowledge.json"
    path_store = tmp_path / "opportunities.json"
    kb1, store1 = KnowledgeBase(path_kb), OpportunityStore(path_store)
    store1.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))
    _link(kb1, "prostadine::vendorB", "prostadine::vendorA")
    del kb1, store1

    kb2, store2 = KnowledgeBase(path_kb), OpportunityStore(path_store)
    assert resolve_canonical_subject("prostadine::vendorA", "affiliate", kb2, store2) == "prostadine::vendorB"


def test_detect_pinned_identity_conflicts_finds_the_real_pair(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="prostadine::vendorB", description="d", category="affiliate"))
    _link(kb, "prostadine::vendorA", "prostadine::vendorB")

    conflicts = detect_pinned_identity_conflicts(kb, store)

    assert conflicts == [("affiliate", "prostadine::vendorA", "prostadine::vendorB")]


def test_detect_pinned_identity_conflicts_empty_when_no_real_link_exists(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="glucotonic::vendorX", description="d", category="affiliate"))

    assert detect_pinned_identity_conflicts(kb, store) == []


def test_detect_pinned_identity_conflicts_never_crosses_categories(tmp_path):
    kb, store = _kb(tmp_path), _store(tmp_path)
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="prostadine::vendorA", description="d", category="saas"))

    assert detect_pinned_identity_conflicts(kb, store) == []
