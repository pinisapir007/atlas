import inspect

import pytest

from atlas.brain.claims import claim_status
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim, Finding
from atlas.brain.reasoning_claims import (
    MAX_EVIDENCE_PER_REASON_CALL,
    MAX_PRIOR_CLAIMS_PER_REASON_CALL,
    ReasonBoundsExceeded,
    reason,
)


class _FakeReasoningProvider:
    """Mirrors tests/brain/test_evidence_validation.py's _FakeAIProvider
    pattern exactly — same shape, reused rather than reinvented."""

    name = "fake"

    def __init__(self, response: dict):
        self._response = response
        self.calls = []

    def complete_structured(self, prompt, fields):
        self.calls.append((prompt, fields))
        return dict(self._response)


class _RaisingProvider:
    def complete_structured(self, prompt, fields):
        raise RuntimeError("real provider failure")


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _real_finding(kb, description="a real observation", evidence="https://real-source.example/x"):
    f = Finding(source="research", category="affiliate", description=description, evidence=evidence)
    kb.save_finding(f)
    return f


COHERENT_RESPONSE = {
    "coherent_claim_possible": "yes",
    "predicate": "possibly_same_as",
    "object": "",
    "supporting_points": "both listings share the same active ingredient list",
    "counter_considerations": "different vendor names could mean a private-label repackaging, not the same manufacturer",
}

INCOHERENT_RESPONSE = {
    "coherent_claim_possible": "no",
    "predicate": "",
    "object": "",
    "supporting_points": "",
    "counter_considerations": "nothing in the evidence relates these two subjects",
}


def test_reason_saves_claim_when_llm_forms_coherent_claim(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    claim = reason("are these the same product?", "product-a", [finding.id], kb, ai_provider=provider)

    assert claim is not None
    assert claim.predicate == "possibly_same_as"
    assert kb.get_claim(claim.id).predicate == "possibly_same_as"


def test_reason_passes_claim_type_through_unchanged(tmp_path):
    """claim_type (2026-08-16) is never inferred from the LLM's own
    response -- only the caller composing `question` knows what kind of
    assertion is being formed."""
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    claim = reason("are these the same product?", "product-a", [finding.id], kb, ai_provider=provider, claim_type="inference")

    assert claim.claim_type == "inference"
    assert kb.get_claim(claim.id).claim_type == "inference"


def test_reason_defaults_claim_type_to_empty_string_when_not_given(tmp_path):
    """Purely additive -- every existing caller/test that never passed
    claim_type keeps the exact original behavior."""
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    claim = reason("are these the same product?", "product-a", [finding.id], kb, ai_provider=provider)

    assert claim.claim_type == ""


def test_reason_returns_none_when_llm_cannot_form_a_coherent_claim(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    provider = _FakeReasoningProvider(INCOHERENT_RESPONSE)

    claim = reason("are these related at all?", "product-a", [finding.id], kb, ai_provider=provider)

    assert claim is None
    assert kb.claims() == []


def test_reason_returns_none_when_predicate_is_empty_even_if_marked_coherent(tmp_path):
    """Fail-closed on a malformed/incomplete structured response — never
    guess a predicate that wasn't actually given."""
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    malformed = {**COHERENT_RESPONSE, "predicate": "  "}
    provider = _FakeReasoningProvider(malformed)

    claim = reason("question", "s", [finding.id], kb, ai_provider=provider)

    assert claim is None


def test_reason_saves_coherent_hypothesis_even_with_no_evidence_passed(tmp_path):
    """Design Lock §1: a coherent hypothesis must be remembered even when
    there is not yet enough evidence to conclude — reason() must not
    discard it just because evidence_finding_ids is thin or empty."""
    kb = _kb(tmp_path)
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    claim = reason("might these share an underlying cause?", "cluster-1", [], kb, ai_provider=provider)

    assert claim is not None
    reloaded = kb.get_claim(claim.id)
    assert reloaded.evidence_finding_ids == []
    assert claim_status(reloaded) == "insufficient_evidence"


def test_reason_prior_claims_are_labeled_as_hypothesis_not_fact_in_the_prompt(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    prior = Claim(subject_id="cluster-1", predicate="discriminates_by", object_value="protein_source")
    kb.save_claim(prior)
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    reason("is this discriminator relevant here too?", "cluster-1", [finding.id], kb, prior_claim_ids=[prior.id], ai_provider=provider)

    assert len(provider.calls) == 1
    prompt, _fields = provider.calls[0]
    assert "NOT yet re-validated" in prompt
    assert "discriminates_by" in prompt
    assert "protein_source" in prompt


def test_reason_evidence_bound_is_enforced(tmp_path):
    kb = _kb(tmp_path)
    too_many = [f"finding-{i}" for i in range(MAX_EVIDENCE_PER_REASON_CALL + 1)]
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    with pytest.raises(ReasonBoundsExceeded):
        reason("q", "s", too_many, kb, ai_provider=provider)
    assert provider.calls == []  # bound checked before any real call is spent


def test_reason_prior_claims_bound_is_enforced(tmp_path):
    kb = _kb(tmp_path)
    too_many = [f"claim-{i}" for i in range(MAX_PRIOR_CLAIMS_PER_REASON_CALL + 1)]
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    with pytest.raises(ReasonBoundsExceeded):
        reason("q", "s", [], kb, prior_claim_ids=too_many, ai_provider=provider)
    assert provider.calls == []


def test_reason_never_expands_evidence_beyond_what_was_explicitly_passed(tmp_path):
    kb = _kb(tmp_path)
    passed = _real_finding(kb, description="passed in")
    _real_finding(kb, description="not passed in, must never leak into the claim")
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    claim = reason("q", "s", [passed.id], kb, ai_provider=provider)

    assert claim.evidence_finding_ids == [passed.id]


def test_reason_caller_supplied_object_id_wins_over_llm_object_answer(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    response_with_object_text = {**COHERENT_RESPONSE, "object": "some free-text the LLM proposed"}
    provider = _FakeReasoningProvider(response_with_object_text)

    claim = reason("q", "product-a", [finding.id], kb, object_id="product-b", ai_provider=provider)

    assert claim.object_id == "product-b"
    assert claim.object_value is None


def test_reason_provider_failure_propagates_never_silently_swallowed(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)

    with pytest.raises(RuntimeError):
        reason("q", "s", [finding.id], kb, ai_provider=_RaisingProvider())
    assert kb.claims() == []


def test_reason_source_is_tagged_reason_llm(tmp_path):
    kb = _kb(tmp_path)
    finding = _real_finding(kb)
    provider = _FakeReasoningProvider(COHERENT_RESPONSE)

    claim = reason("q", "s", [finding.id], kb, ai_provider=provider)

    assert claim.source == "reason_llm"
    assert claim.question == "q"


# --- structural firewall: reasoning_claims.py can never dispatch an action --


def test_reasoning_claims_module_never_imports_delegator_registry_or_riskpolicy():
    """Structural firewall, same inspect.getsource() technique already
    proven for browser_scroll_advancer.py's click/input/navigate
    exclusion — checks actual import statements, not any prose mention
    (this module's own docstring explains the firewall in words, which
    would otherwise trip a naive substring check)."""
    import atlas.brain.reasoning_claims as module

    source = inspect.getsource(module)
    forbidden_imports = (
        "atlas.brain.delegator",
        "atlas.core.registry",
        "atlas.brain.risk",
    )
    for forbidden in forbidden_imports:
        assert f"import {forbidden}" not in source, f"reasoning_claims.py must never import {forbidden!r}"
        assert f"from {forbidden}" not in source, f"reasoning_claims.py must never import from {forbidden!r}"
