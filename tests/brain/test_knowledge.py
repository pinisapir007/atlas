import pytest

from atlas.brain.future_items import UNWIRED_TRIGGER_CHECK
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, FutureItem, SuccessLaw


def test_round_trips_a_finding(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    finding = Finding(source="research", category="affiliate", description="a real affiliate program")
    kb.save_finding(finding)

    reloaded = KnowledgeBase(tmp_path / "knowledge.json").get_finding(finding.id)
    assert reloaded.description == "a real affiliate program"
    assert reloaded.source == "research"


def test_findings_persist_across_instances(tmp_path):
    path = tmp_path / "knowledge.json"
    KnowledgeBase(path).save_finding(Finding(source="research", category="youtube", description="a real niche"))

    assert len(KnowledgeBase(path).findings()) == 1


def test_evidence_defaults_to_empty_not_fabricated(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    finding = Finding(source="research", category="ugc", description="an idea with no real source yet")
    kb.save_finding(finding)

    assert kb.get_finding(finding.id).evidence == ""


def test_missing_finding_raises_keyerror(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(KeyError):
        kb.get_finding("does-not-exist")


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "knowledge.json"
    kb = KnowledgeBase(path)
    kb.save_finding(Finding(source="research", category="affiliate", description="x"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()


# --- Filtered Knowledge Retrieval seam (2026-08-15, Foundation Design) --


def _seed_findings(kb: KnowledgeBase) -> dict:
    """Four real, distinguishable findings covering every filter
    dimension, plus overlaps -- enough to prove single filters, AND
    combinations, and zero-match cases without ambiguity."""
    a = Finding(source="s1", category="affiliate", description="a", provider="digistore24", subject="ketodna")
    b = Finding(source="s2", category="affiliate", description="b", provider="digistore24", subject="other")
    c = Finding(source="s3", category="affiliate", description="c", provider="shareasale", subject="ketodna")
    d = Finding(source="s4", category="digital_product", description="d", provider="digistore24", subject="ketodna")
    for f in (a, b, c, d):
        kb.save_finding(f)
    return {"a": a, "b": b, "c": c, "d": d}


def test_findings_with_no_filters_returns_everything_unchanged(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    seeded = _seed_findings(kb)

    assert {f.id for f in kb.findings()} == {f.id for f in seeded.values()}


def test_findings_filtered_by_category_only(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    seeded = _seed_findings(kb)

    result = kb.findings(category="affiliate")

    assert {f.id for f in result} == {seeded["a"].id, seeded["b"].id, seeded["c"].id}


def test_findings_filtered_by_provider_only(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    seeded = _seed_findings(kb)

    result = kb.findings(provider="digistore24")

    assert {f.id for f in result} == {seeded["a"].id, seeded["b"].id, seeded["d"].id}


def test_findings_filtered_by_subject_only(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    seeded = _seed_findings(kb)

    result = kb.findings(subject="ketodna")

    assert {f.id for f in result} == {seeded["a"].id, seeded["c"].id, seeded["d"].id}


def test_findings_multiple_filters_combine_with_and(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    seeded = _seed_findings(kb)

    result = kb.findings(category="affiliate", provider="digistore24", subject="ketodna")

    assert [f.id for f in result] == [seeded["a"].id]


def test_findings_zero_matches_returns_empty_list(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    _seed_findings(kb)

    assert kb.findings(category="youtube") == []
    assert kb.findings(category="affiliate", provider="shareasale", subject="other") == []


def test_findings_result_order_matches_unfiltered_order(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    seeded = _seed_findings(kb)

    unfiltered_order = [f.id for f in kb.findings()]
    filtered_order = [f.id for f in kb.findings(category="affiliate")]

    assert filtered_order == [fid for fid in unfiltered_order if fid in {seeded["a"].id, seeded["b"].id, seeded["c"].id}]


def test_market_is_not_a_supported_filter():
    """Deliberate: a real grep across the codebase found Finding.market is
    only ever read/reported, never filtered on anywhere -- adding a
    market= parameter would be speculative, not justified by real usage,
    per the standing 'future is not a parking lot, but do not build ahead
    of evidence either' discipline."""
    import inspect

    params = inspect.signature(KnowledgeBase.findings).parameters
    assert "market" not in params


# --- SuccessLaw -------------------------------------------------------


def test_round_trips_a_success_law(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    finding = Finding(source="research", category="affiliate", description="x", evidence="https://x/1")
    kb.save_finding(finding)
    law = SuccessLaw(
        principle="First-person testimonial framing outperforms feature-listing for consumer health products",
        source_description="Analysis of a real, publicly posted testimonial-style video",
        evidence_finding_ids=[finding.id],
        applicable_business_models=["affiliate", "digital_product"],
    )
    kb.save_success_law(law)

    reloaded = KnowledgeBase(tmp_path / "knowledge.json").get_success_law(law.id)
    assert reloaded.principle == law.principle
    assert reloaded.evidence_finding_ids == [finding.id]
    assert reloaded.applicable_business_models == ["affiliate", "digital_product"]


def test_success_laws_persist_across_instances(tmp_path):
    path = tmp_path / "knowledge.json"
    KnowledgeBase(path).save_success_law(SuccessLaw(principle="p", source_description="s"))

    assert len(KnowledgeBase(path).success_laws()) == 1


def test_success_law_evidence_defaults_to_empty_not_fabricated(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    law = SuccessLaw(principle="p", source_description="s")
    kb.save_success_law(law)

    assert kb.get_success_law(law.id).evidence_finding_ids == []


def test_missing_success_law_raises_keyerror(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(KeyError, match="no such success law"):
        kb.get_success_law("does-not-exist")


def test_success_laws_tolerates_a_knowledge_file_saved_before_success_laws_existed(tmp_path):
    # An old knowledge.json with only "findings" (no "success_laws" key at
    # all) must not crash -- confirms the .get(..., {}) fallback works.
    import json

    path = tmp_path / "knowledge.json"
    KnowledgeBase(path).save_finding(Finding(source="research", category="affiliate", description="x"))
    data = json.loads(path.read_text())
    data.pop("success_laws", None)
    path.write_text(json.dumps(data))

    kb = KnowledgeBase(path)
    assert kb.success_laws() == []
    kb.save_success_law(SuccessLaw(principle="p", source_description="s"))
    assert len(kb.success_laws()) == 1


# --- FutureItem ---------------------------------------------------------


def _future_item(**overrides) -> FutureItem:
    defaults = dict(
        type="candidate",
        title="Funnel-stage measurement",
        rationale="Real gap identified while researching an external funnel/copywriting case study",
        trigger_description="Not yet wired to a real predicate",
        trigger_check=UNWIRED_TRIGGER_CHECK,
    )
    defaults.update(overrides)
    return FutureItem(**defaults)


def test_round_trips_a_future_item(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    item = _future_item()
    kb.save_future_item(item)

    reloaded = KnowledgeBase(tmp_path / "knowledge.json").get_future_item(item.id)
    assert reloaded.title == item.title
    assert reloaded.type == "candidate"
    assert reloaded.status == "open"
    assert reloaded.trigger_check == UNWIRED_TRIGGER_CHECK


def test_future_items_persist_across_instances(tmp_path):
    path = tmp_path / "knowledge.json"
    KnowledgeBase(path).save_future_item(_future_item())

    assert len(KnowledgeBase(path).future_items()) == 1


def test_missing_future_item_raises_keyerror(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(KeyError, match="no such future item"):
        kb.get_future_item("does-not-exist")


def test_future_items_tolerates_a_knowledge_file_saved_before_future_items_existed(tmp_path):
    import json

    path = tmp_path / "knowledge.json"
    KnowledgeBase(path).save_finding(Finding(source="research", category="affiliate", description="x"))
    data = json.loads(path.read_text())
    data.pop("future_items", None)
    path.write_text(json.dumps(data))

    kb = KnowledgeBase(path)
    assert kb.future_items() == []
    kb.save_future_item(_future_item())
    assert len(kb.future_items()) == 1


def test_save_future_item_rejects_unknown_type(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(ValueError, match="unknown FutureItem type"):
        kb.save_future_item(_future_item(type="idea"))


def test_save_future_item_rejects_unknown_status(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(ValueError, match="unknown FutureItem status"):
        kb.save_future_item(_future_item(status="in_progress"))


def test_save_future_item_rejects_unknown_resolution(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(ValueError, match="unknown FutureItem resolution"):
        kb.save_future_item(_future_item(status="resolved", resolution="maybe"))


def test_save_future_item_rejects_unregistered_trigger_check(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    with pytest.raises(ValueError, match="unknown trigger_check"):
        kb.save_future_item(_future_item(trigger_check="some_made_up_predicate_name"))


def test_save_future_item_accepts_unwired_trigger_check(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    kb.save_future_item(_future_item(trigger_check=UNWIRED_TRIGGER_CHECK))

    assert len(kb.future_items()) == 1


def test_save_future_item_accepts_none_resolution_by_default(tmp_path):
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    kb.save_future_item(_future_item())

    assert kb.future_items()[0].resolution is None
