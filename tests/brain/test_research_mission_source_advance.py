from dataclasses import dataclass

from atlas.brain.browser_plugin import DomainNotApprovedError
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_research import EvidenceQualityRejected
from atlas.brain.models import Finding
from atlas.brain.research_mission_source_advance import (
    advance_research_mission_sources,
)
from atlas.brain.research_missions import (
    ResearchMission,
    ResearchMissionStore,
)


@dataclass
class _Plugin:
    name: str


def _setup(tmp_path, *, attempts=2):
    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )
    knowledge = KnowledgeBase(
        tmp_path / "knowledge.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad digital research",
        max_attempts_per_source=attempts,
    )
    store.save_mission(mission)

    return store, knowledge, mission


def test_flag_off_is_exact_noop(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        raising=False,
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Research UGC demand",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )

    changed = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert changed == []

    restored = store.get_source(source.id)
    assert restored.status == "pending"
    assert restored.attempts == 0


def test_success_marks_processed_and_links_findings(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Research UGC demand",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )

    captured = {}

    def fake_collect(**kwargs):
        captured.update(kwargs)

        return [
            Finding(
                id="finding-a",
                source="research_mission",
                category="ugc",
                description="real A",
                evidence="https://example.com/report",
            ),
            Finding(
                id="finding-b",
                source="research_mission",
                category="ugc",
                description="real B",
                evidence="https://example.com/report",
            ),
        ]

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        fake_collect,
    )

    changed = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert len(changed) == 1

    restored = store.get_source(source.id)

    assert restored.status == "processed"
    assert restored.attempts == 1
    assert restored.finding_ids == [
        "finding-a",
        "finding-b",
    ]
    assert restored.last_error == ""

    assert captured["source_ref"] == "https://example.com/report"
    assert captured["category"] == "ugc"
    assert captured["task_description"] == "Research UGC demand"
    assert captured["source"] == "research_mission"
    assert captured["provider"] == "browser"


def test_zero_verified_findings_is_rejected(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Research UGC demand",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )
    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        lambda **kwargs: [],
    )

    advance_research_mission_sources(
        store,
        knowledge,
    )

    restored = store.get_source(source.id)

    assert restored.status == "rejected"
    assert restored.attempts == 1
    assert restored.finding_ids == []
    assert "zero verified atomic Findings" in restored.last_error


def test_epistemic_rejection_is_terminal(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Research UGC demand",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )

    def reject(**kwargs):
        raise EvidenceQualityRejected("off task")

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        reject,
    )

    advance_research_mission_sources(
        store,
        knowledge,
    )

    restored = store.get_source(source.id)

    assert restored.status == "rejected"
    assert restored.attempts == 1
    assert "EvidenceQualityRejected" in restored.last_error


def test_unapproved_domain_is_terminal_rejection(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "https://unapproved.example/report",
        "ugc",
        "Research UGC demand",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )

    def reject(**kwargs):
        raise DomainNotApprovedError("not approved")

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        reject,
    )

    advance_research_mission_sources(
        store,
        knowledge,
    )

    restored = store.get_source(source.id)

    assert restored.status == "rejected"
    assert restored.attempts == 1
    assert "DomainNotApprovedError" in restored.last_error


def test_transient_failure_retries_then_exhausts(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(
        tmp_path,
        attempts=2,
    )

    source = store.add_source(
        mission.id,
        "https://example.com/report",
        "ugc",
        "Research UGC demand",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )

    def fail(**kwargs):
        raise RuntimeError("temporary backend failure")

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        fail,
    )

    first = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert len(first) == 1

    restored = store.get_source(source.id)

    assert restored.status == "pending"
    assert restored.attempts == 1

    second = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert len(second) == 1

    restored = store.get_source(source.id)

    assert restored.status == "failed_exhausted"
    assert restored.attempts == 2
    assert "RuntimeError" in restored.last_error


def test_youtube_is_left_for_specialized_bridge(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "https://youtube.com/watch?v=abc",
        "ugc",
        "Research UGC video evidence",
        source_kind="browser",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("youtube"),
    )

    def should_not_run(**kwargs):
        raise AssertionError(
            "generic collector must not process YouTube"
        )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        should_not_run,
    )

    changed = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert changed == []

    restored = store.get_source(source.id)

    assert restored.status == "pending"
    assert restored.attempts == 0


def test_unsupported_source_is_rejected(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    source = store.add_source(
        mission.id,
        "unsupported://thing",
        "ugc",
        "Research UGC demand",
    )

    def unsupported(ref):
        raise ValueError("no plugin")

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        unsupported,
    )

    advance_research_mission_sources(
        store,
        knowledge,
    )

    restored = store.get_source(source.id)

    assert restored.status == "rejected"
    assert restored.attempts == 1
    assert "unsupported source_ref" in restored.last_error


def test_one_source_per_call_bound(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store, knowledge, mission = _setup(tmp_path)

    first = store.add_source(
        mission.id,
        "https://example.com/a",
        "ugc",
        "Check A",
    )
    second = store.add_source(
        mission.id,
        "https://example.com/b",
        "ugc",
        "Check B",
    )

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance.select_plugin",
        lambda ref: _Plugin("browser"),
    )

    def fake_collect(**kwargs):
        return [
            Finding(
                source="research_mission",
                category="ugc",
                description="real",
                evidence=kwargs["source_ref"],
            )
        ]

    monkeypatch.setattr(
        "atlas.brain.research_mission_source_advance."
        "collect_atomic_evidence_from_source",
        fake_collect,
    )

    changed = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert len(changed) == 1

    statuses = {
        item.id: item.status
        for item in store.sources(mission.id)
    }

    assert statuses[first.id] == "processed"
    assert statuses[second.id] == "pending"
