import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding


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
