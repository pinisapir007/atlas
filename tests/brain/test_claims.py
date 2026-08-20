import pytest

from atlas.brain.claims import claim_confidence, claim_status
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim, Finding


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _real_finding(kb, evidence="https://real-source.example/x"):
    f = Finding(source="research", category="affiliate", description="a real observation", evidence=evidence)
    kb.save_finding(f)
    return f


# --- persistence / round-trip ---------------------------------------------


def test_claim_round_trips_through_knowledge_base(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    claim = Claim(subject_id="opp-1", predicate="possibly_same_as", object_id="opp-2", evidence_finding_ids=[finding.id])
    kb.save_claim(claim)

    reloaded = KnowledgeBase(tmp_path / "knowledge.json").get_claim(claim.id)
    assert reloaded.predicate == "possibly_same_as"
    assert reloaded.object_id == "opp-2"
    assert reloaded.evidence_finding_ids == [finding.id]


def test_missing_claim_raises_keyerror(tmp_path):
    kb = _kb(tmp_path)
    with pytest.raises(KeyError):
        kb.get_claim("does-not-exist")


# --- self-contamination firewall ------------------------------------------


def test_save_claim_rejects_evidence_finding_id_that_is_not_a_real_finding(tmp_path):
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="has_attribute", object_value="x", evidence_finding_ids=["not-real"])
    with pytest.raises(KeyError):
        kb.save_claim(claim)


def test_save_claim_rejects_a_claim_id_used_as_its_own_evidence(tmp_path):
    """The structural self-contamination firewall (Design Lock §2): an
    LLM-produced Claim's own content can never become evidence for
    another Claim — evidence_finding_ids must resolve to a real Finding,
    never a Claim, even if the id looks superficially valid."""
    kb = _kb(tmp_path)
    claim_a = Claim(subject_id="s", predicate="suspected", object_value="x")
    kb.save_claim(claim_a)

    claim_b = Claim(subject_id="s2", predicate="confirms", object_value="y", evidence_finding_ids=[claim_a.id])
    with pytest.raises(KeyError):
        kb.save_claim(claim_b)


def test_save_claim_rejects_unknown_prior_claim_id(tmp_path):
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="x", prior_claim_ids=["not-real"])
    with pytest.raises(KeyError):
        kb.save_claim(claim)


# --- schema validation ------------------------------------------------------


def test_save_claim_rejects_both_object_id_and_object_value_set(tmp_path):
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="x", object_id="e1", object_value="literal")
    with pytest.raises(ValueError):
        kb.save_claim(claim)


def test_save_claim_rejects_empty_predicate(tmp_path):
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="   ")
    with pytest.raises(ValueError):
        kb.save_claim(claim)


def test_unary_claim_with_neither_object_id_nor_value_is_valid(tmp_path):
    """A claim about subject_id alone (e.g. predicate="needs_investigation")
    is not ambiguous — only setting BOTH object fields is."""
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="needs_investigation")
    kb.save_claim(claim)  # must not raise

    assert kb.get_claim(claim.id).object_id is None
    assert kb.get_claim(claim.id).object_value is None


def test_new_predicate_requires_no_schema_change(tmp_path):
    """predicate is an open string, the same convention Finding.category
    already establishes — a wholly novel predicate saves fine, no
    enum/schema update needed anywhere."""
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="rhymes_suspiciously_with", object_value="a made-up relation kind")
    kb.save_claim(claim)

    assert kb.get_claim(claim.id).predicate == "rhymes_suspiciously_with"


# --- claim_status() ----------------------------------------------------------


def test_claim_status_supported_when_real_evidence_present_and_no_contradiction(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    claim = Claim(subject_id="s", predicate="x", evidence_finding_ids=[finding.id])

    assert claim_status(claim) == "supported"


def test_coherent_hypothesis_with_no_evidence_is_insufficient_evidence_not_discarded(tmp_path):
    """Design Lock §1: 'UNKNOWN IS KNOWLEDGE ABOUT WHAT WE DO NOT YET
    KNOW' — a claim can legitimately be saved with zero evidence and
    still be a real, retrievable, remembered hypothesis."""
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="might_be_related_to", object_value="something noticed")
    kb.save_claim(claim)  # empty evidence_finding_ids must be legal

    reloaded = kb.get_claim(claim.id)
    assert reloaded.evidence_finding_ids == []
    assert claim_status(reloaded) == "insufficient_evidence"


def test_claim_status_contradicted_when_only_contradicting_evidence(tmp_path):
    kb = _kb(tmp_path)
    contradicting = _real_finding(kb, evidence="https://real-source.example/contradicts")
    claim = Claim(subject_id="s", predicate="x", contradicted_by_finding_ids=[contradicting.id])

    assert claim_status(claim) == "contradicted"


def test_claim_status_ambiguous_when_both_supporting_and_contradicting_evidence(tmp_path):
    kb = _kb(tmp_path)
    supporting = _real_finding(kb, evidence="https://real-source.example/supports")
    contradicting = _real_finding(kb, evidence="https://real-source.example/contradicts")
    claim = Claim(
        subject_id="s",
        predicate="x",
        evidence_finding_ids=[supporting.id],
        contradicted_by_finding_ids=[contradicting.id],
    )

    assert claim_status(claim) == "ambiguous"


def test_claim_status_superseded_when_superseded_by_id_set(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    old = Claim(subject_id="s", predicate="x", evidence_finding_ids=[finding.id])
    kb.save_claim(old)
    new = Claim(subject_id="s", predicate="x, refined", evidence_finding_ids=[finding.id])
    kb.save_claim(new)

    old.superseded_by_id = new.id
    kb.save_claim(old)

    assert claim_status(kb.get_claim(old.id)) == "superseded"


# --- claim_confidence() -- claim-local only, never a broader scan ----------


def test_claim_confidence_ignores_findings_not_linked_to_this_claim(tmp_path):
    """Design Lock §2: 'A Claim may only gain epistemic support from
    evidence explicitly linked to that Claim.' Several other Findings in
    the same category exist in the KnowledgeBase but were never attached
    to this Claim — they must never inflate its confidence."""
    kb = _kb(tmp_path)
    linked = _real_finding(kb, evidence="https://real-source.example/linked")
    # Three more real findings exist in the KnowledgeBase, same category,
    # but are never referenced by the claim below.
    _real_finding(kb, evidence="https://real-source.example/unrelated-1")
    _real_finding(kb, evidence="https://real-source.example/unrelated-2")
    _real_finding(kb, evidence="https://real-source.example/unrelated-3")

    claim = Claim(subject_id="s", predicate="x", evidence_finding_ids=[linked.id])

    # Claim-local confidence: only 1 real linked finding -> well below the
    # 3-finding saturation sample, never boosted by the other 3 in the KB.
    from atlas.brain.confidence import SOURCE_SATURATION_SAMPLE

    assert claim_confidence(claim, kb) == pytest.approx(1 / SOURCE_SATURATION_SAMPLE)


def test_claim_confidence_returns_none_when_contradicted(tmp_path):
    """No naive arithmetic (Design Lock §3): 3 supports + 1 contradiction
    must never resolve to 'still mostly true'."""
    kb = _kb(tmp_path)
    supports = [_real_finding(kb, evidence=f"https://real-source.example/s{i}") for i in range(3)]
    contradicting = _real_finding(kb, evidence="https://real-source.example/contradicts")
    claim = Claim(
        subject_id="s",
        predicate="x",
        evidence_finding_ids=[f.id for f in supports],
        contradicted_by_finding_ids=[contradicting.id],
    )

    assert claim_confidence(claim, kb) is None


def test_claim_confidence_returns_none_when_no_evidence(tmp_path):
    claim = Claim(subject_id="s", predicate="x")
    kb = _kb(tmp_path)

    assert claim_confidence(claim, kb) is None


# --- revision / audit trail --------------------------------------------------


def test_unresolved_claim_can_later_be_superseded_without_losing_audit_trail(tmp_path):
    kb = _kb(tmp_path)
    old = Claim(subject_id="s", predicate="might_be_related_to", object_value="a hunch")
    kb.save_claim(old)  # starts as insufficient_evidence

    finding = _real_finding(kb)
    new = Claim(subject_id="s", predicate="is_related_to", object_value="confirmed", evidence_finding_ids=[finding.id])
    kb.save_claim(new)
    old.superseded_by_id = new.id
    kb.save_claim(old)

    reloaded_old = kb.get_claim(old.id)
    reloaded_new = kb.get_claim(new.id)
    assert reloaded_old.predicate == "might_be_related_to"  # original content untouched
    assert reloaded_old.superseded_by_id == new.id
    assert claim_status(reloaded_old) == "superseded"
    assert claim_status(reloaded_new) == "supported"


# --- claim_type -- orthogonal axis to claim_status() (2026-08-16) ----------


def test_claim_type_defaults_to_unclassified_empty_string(tmp_path):
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="x")
    kb.save_claim(claim)

    assert kb.get_claim(claim.id).claim_type == ""


def test_claim_type_is_settable_and_round_trips(tmp_path):
    kb = _kb(tmp_path)
    claim = Claim(subject_id="s", predicate="means", object_value="y", claim_type="observation")
    kb.save_claim(claim)

    assert kb.get_claim(claim.id).claim_type == "observation"


def test_claim_type_and_claim_status_are_independent_axes(tmp_path):
    """The exact scenario from the founder's own example: a near-direct
    observation and a speculative inference can both be real, evidenced,
    'supported' claims (claim_status) while being totally different KINDS
    of assertion (claim_type) -- neither axis may collapse into the
    other."""
    kb = _kb(tmp_path)
    finding = _real_finding(kb)

    observation = Claim(
        subject_id="digistore24_marketplace:field:commission_pct",
        predicate="means",
        object_value="the affiliate's share of the vendor's earnings",
        evidence_finding_ids=[finding.id],
        claim_type="observation",
    )
    inference = Claim(
        subject_id="product-x",
        predicate="is_attractive_because_of_commission",
        object_value="60% commission is high",
        evidence_finding_ids=[finding.id],
        claim_type="inference",
    )
    kb.save_claim(observation)
    kb.save_claim(inference)

    # Same evidence-status (both real evidence, no contradiction)...
    assert claim_status(kb.get_claim(observation.id)) == "supported"
    assert claim_status(kb.get_claim(inference.id)) == "supported"
    # ...but a completely different claim_type -- never merged/derived from claim_status.
    assert kb.get_claim(observation.id).claim_type == "observation"
    assert kb.get_claim(inference.id).claim_type == "inference"


def test_claim_type_never_affects_claim_status_computation(tmp_path):
    """claim_status() must remain a pure function of evidence/contradiction/
    supersession fields only -- claim_type is never consulted by it."""
    kb = _kb(tmp_path)
    hypothesis = Claim(subject_id="s", predicate="might_be_related_to", object_value="a hunch", claim_type="hypothesis")
    kb.save_claim(hypothesis)

    assert claim_status(kb.get_claim(hypothesis.id)) == "insufficient_evidence"


def test_existing_claims_without_claim_type_remain_fully_compatible(tmp_path):
    """Backward compatibility: a Claim constructed exactly as every
    pre-existing caller/test already does (no claim_type argument at all)
    must keep working unchanged."""
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    claim = Claim(subject_id="opp-1", predicate="possibly_same_as", object_id="opp-2", evidence_finding_ids=[finding.id])
    kb.save_claim(claim)

    reloaded = kb.get_claim(claim.id)
    assert reloaded.claim_type == ""
    assert claim_status(reloaded) == "supported"


# --- identity vs. similarity vs. substitute never conflated -----------------


def test_similarity_and_identity_predicates_coexist_independently(tmp_path):
    """Design Lock §5: A possibly_same_as B and A similar_to B must be
    able to coexist without one overwriting or implying the other."""
    kb = _kb(tmp_path)
    identity_claim = Claim(subject_id="product-a", predicate="possibly_same_as", object_id="product-b")
    similarity_claim = Claim(subject_id="product-a", predicate="similar_to", object_id="product-b")
    kb.save_claim(identity_claim)
    kb.save_claim(similarity_claim)

    claims_about_a = kb.claims(subject_id="product-a")
    predicates = {c.predicate for c in claims_about_a}
    assert predicates == {"possibly_same_as", "similar_to"}
