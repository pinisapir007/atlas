import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, SuccessLaw


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
