from atlas.brain.investigation_advance import advance_investigations
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Investigation
from atlas.integrations.base import PageObservation


class _FakePlugin:
    name = "fake"

    def __init__(self, observation):
        self._observation = observation

    def can_handle(self, source_ref):
        return True

    def observe(self, source_ref, extract=None):
        return self._observation


class _FakeAIProvider:
    def __init__(self, relevant: bool, subject_match: str):
        self._relevant = relevant
        self._subject_match = subject_match

    def complete_structured(self, prompt, fields):
        if "verdict" in fields:
            return {"verdict": self._subject_match, "reason": "fake"}
        return {"relevant": "yes" if self._relevant else "no", "reason": "fake"}


def _long_text(marker="real evidence") -> str:
    return f"{marker} " * 20


def _investigation(**overrides) -> Investigation:
    defaults = dict(subject_id="prostadine::vendorA", category="affiliate", status="waiting_for_evidence", missing_evidence="independent confirmation")
    defaults.update(overrides)
    return Investigation(**defaults)


def test_g_verified_returned_evidence_updates_investigation_correctly(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as ksr

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    store = InvestigationStore(tmp_path / "investigations.json")
    investigation = _investigation()
    store.save_investigation(investigation)

    plugin = _FakePlugin(PageObservation(url="https://example.com", title="Prostadine", text_content=_long_text("real Prostadine content")))
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: plugin)

    changed = advance_investigations(
        store, knowledge, source_refs={investigation.id: "https://example.com/prostadine"},
        ai_provider=_FakeAIProvider(relevant=True, subject_match="same"),
    )

    assert len(changed) == 1
    reloaded = store.get_investigation(investigation.id)
    assert reloaded.status == "ready_for_evaluation"
    assert len(reloaded.supporting_finding_ids) == 1
    assert knowledge.get_finding(reloaded.supporting_finding_ids[0]).subject == "prostadine::vendorA"


def test_h_no_concrete_source_ref_fails_closed_and_waits(tmp_path):
    """Test H: must never invent a URL."""
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    store = InvestigationStore(tmp_path / "investigations.json")
    investigation = _investigation()
    store.save_investigation(investigation)

    changed = advance_investigations(store, knowledge, source_refs={})

    assert changed == []
    reloaded = store.get_investigation(investigation.id)
    assert reloaded.status == "waiting_for_evidence"  # untouched, not stuck-in-error, not fabricated
    assert reloaded.supporting_finding_ids == []


def test_wrong_product_observation_never_advances_the_investigation(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as ksr

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    store = InvestigationStore(tmp_path / "investigations.json")
    investigation = _investigation()
    store.save_investigation(investigation)

    plugin = _FakePlugin(PageObservation(url="https://example.com", title="Glucotonic", text_content=_long_text("real glucotonic content")))
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: plugin)

    changed = advance_investigations(
        store, knowledge, source_refs={investigation.id: "https://example.com/glucotonic"},
        ai_provider=_FakeAIProvider(relevant=True, subject_match="different"),
    )

    assert changed == []
    reloaded = store.get_investigation(investigation.id)
    assert reloaded.status == "waiting_for_evidence"
    assert reloaded.supporting_finding_ids == []
    assert knowledge.findings() == []


def test_only_waiting_for_evidence_investigations_are_considered(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    store = InvestigationStore(tmp_path / "investigations.json")
    open_one = _investigation(status="open", subject_id="x")
    closed_one = _investigation(status="closed", subject_id="y")
    store.save_investigation(open_one)
    store.save_investigation(closed_one)

    changed = advance_investigations(
        store, knowledge,
        source_refs={open_one.id: "https://example.com/x", closed_one.id: "https://example.com/y"},
    )

    assert changed == []
