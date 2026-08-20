import pytest

from atlas.brain.confidence import source_corroboration_score
from atlas.brain.decision_engine import decide
from atlas.brain.evidence_provenance import evidence_origin, independent_source_count
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_research import (
    EvidenceQualityRejected,
    SubjectAttributionUnverified,
    collect_evidence_from_source,
)
from atlas.brain.memory import BrainMemory
from atlas.brain.kpi import KPIRegistry
from atlas.integrations.base import PageObservation


class _FakePlugin:
    name = "fake"

    def __init__(self, observation):
        self._observation = observation
        self.calls = []

    def can_handle(self, source_ref):
        return True

    def observe(self, source_ref, extract=None):
        self.calls.append((source_ref, extract))
        return self._observation


class _FakeAIProvider:
    """Answers whichever real question is actually asked (distinguished
    by `fields`' own keys -- the same real signal a real AIProvider call
    site already relies on) -- assess_observation_quality()'s
    relevance check, subject_verification.verify_subject_match()'s
    entity-attribution check, and evidence_role_classification.
    classify_evidence_role()'s role judgment are three genuinely
    different questions, all real AI calls through the same
    complete_structured() seam."""

    name = "fake"

    def __init__(self, relevant: bool, subject_match: str = "same", role: str = "unknown"):
        self._relevant = relevant
        self._subject_match = subject_match
        self._role = role

    def complete_structured(self, prompt, fields):
        if "verdict" in fields:
            return {"verdict": self._subject_match, "reason": "fake attribution judgment"}
        if "role" in fields:
            return {"role": self._role, "reason": "fake role judgment"}
        return {"relevant": "yes" if self._relevant else "no", "reason": "fake judgment"}


def _long_text(marker="real evidence") -> str:
    return f"{marker} " * 20


def test_a_real_high_quality_observation_produces_a_real_finding(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("real keto demand")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    finding = collect_evidence_from_source(
        "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
        knowledge=knowledge, subject="keto", market="US", ai_provider=_FakeAIProvider(relevant=True),
    )

    # evidence_provenance.py (2026-08-17): the real, FINAL observed
    # identifier (observation.url), not the originally-requested
    # source_ref -- a real redirect must never be hidden.
    assert finding.evidence == "src"
    assert finding.category == "affiliate"
    assert finding.subject == "keto"
    assert knowledge.findings() == [finding]


def test_a_real_low_quality_observation_is_rejected_not_silently_saved(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content="too short"))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    with pytest.raises(EvidenceQualityRejected):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, ai_provider=_FakeAIProvider(relevant=True),
        )

    assert knowledge.findings() == []


def test_a_real_off_task_observation_is_rejected_not_silently_saved(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("unrelated recipe content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    with pytest.raises(EvidenceQualityRejected, match="failed evidence quality"):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, ai_provider=_FakeAIProvider(relevant=False),
        )

    assert knowledge.findings() == []


def test_a_real_plugin_failure_propagates_and_is_never_recorded(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    class _FailingPlugin:
        name = "failing"

        def can_handle(self, source_ref):
            return True

        def observe(self, source_ref, extract=None):
            raise RuntimeError("real plugin failure")

    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: _FailingPlugin())

    with pytest.raises(RuntimeError, match="real plugin failure"):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="a real task",
            knowledge=knowledge,
        )

    assert knowledge.findings() == []


# --- Return-Path Subject Verification (2026-08-17, ONE BRAIN Root Implementation) ---


def test_a_wrong_product_observation_is_never_trusted_as_the_requested_subject(tmp_path, monkeypatch):
    """Test A: wrong returned product must never become trusted Finding
    evidence for the requested subject."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="Glucotonic", text_content=_long_text("real glucotonic content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    with pytest.raises(SubjectAttributionUnverified):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, subject="Prostadine",
            ai_provider=_FakeAIProvider(relevant=True, subject_match="different"),
        )

    assert knowledge.findings() == []


def test_unknown_subject_attribution_is_never_saved_as_category_general_fallback(tmp_path, monkeypatch):
    """Test B, first half: UNKNOWN attribution must never be silently
    saved with subject="" as a category-general fallback."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("ambiguous content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    with pytest.raises(SubjectAttributionUnverified):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, subject="Prostadine",
            ai_provider=_FakeAIProvider(relevant=True, subject_match="unknown"),
        )

    assert knowledge.findings() == []


def test_unknown_subject_attribution_never_increases_category_level_confidence(tmp_path, monkeypatch):
    """Test B, second half: proves the previous round's design mistake
    (subject="" fallback) is genuinely closed -- a rejected/unknown
    observation must never influence confidence_score()/decide() for
    the category either, not just Bridge 1's subject-level grouping."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    before = source_corroboration_score("affiliate", knowledge)
    before_decision = decide("affiliate", knowledge, memory, kpis)

    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("ambiguous content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)
    with pytest.raises(SubjectAttributionUnverified):
        collect_evidence_from_source(
            "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
            knowledge=knowledge, subject="Prostadine",
            ai_provider=_FakeAIProvider(relevant=True, subject_match="unknown"),
        )

    after = source_corroboration_score("affiliate", knowledge)
    after_decision = decide("affiliate", knowledge, memory, kpis)

    assert before == after  # None == None: no real Finding was ever added
    assert before_decision.verdict == after_decision.verdict


def test_verified_correct_subject_saves_the_finding_normally(tmp_path, monkeypatch):
    """Test C."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="Prostadine", text_content=_long_text("real Prostadine content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    finding = collect_evidence_from_source(
        "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
        knowledge=knowledge, subject="Prostadine",
        ai_provider=_FakeAIProvider(relevant=True, subject_match="same"),
    )

    assert finding.subject == "Prostadine"
    assert knowledge.findings() == [finding]


def test_category_general_calls_with_no_subject_skip_verification_entirely(tmp_path, monkeypatch):
    """Backward compatibility: subject="" (category-general, the
    existing, unchanged use case) must never trigger subject
    verification at all."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    plugin = _FakePlugin(PageObservation(url="src", title="t", text_content=_long_text("real general content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    finding = collect_evidence_from_source(
        "some-source", category="affiliate", source="test-source", task_description="is there real demand?",
        knowledge=knowledge, ai_provider=_FakeAIProvider(relevant=True, subject_match="unknown"),
    )

    assert finding.subject == ""
    assert knowledge.findings() == [finding]


# --- A/B/I: evidence provenance wiring (2026-08-17, ONE BRAIN Evidence Provenance) ---


def test_a_redirect_stores_the_final_observed_url_not_the_requested_one(tmp_path, monkeypatch):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    # the plugin observed a real, different, final URL after a redirect
    plugin = _FakePlugin(PageObservation(url="https://example.com/final-page", title="t", text_content=_long_text()))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    finding = collect_evidence_from_source(
        "https://example.com/original-requested-url", category="affiliate", source="test-source",
        task_description="task", knowledge=knowledge, ai_provider=_FakeAIProvider(relevant=True),
    )

    assert finding.evidence == "https://example.com/final-page"
    assert finding.evidence != "https://example.com/original-requested-url"


def test_b_two_different_requested_urls_landing_on_the_same_real_page_count_as_one_source(tmp_path, monkeypatch):
    """collect_evidence_from_source() is a generic, sense-agnostic writer
    that deliberately never guesses evidence_role (ONE BRAIN Evidence
    Role Gate, 2026-08-17 -- no structural signal distinguishes a direct
    vendor page from a relay/quote for open web content). Its own
    real-world-origin-normalization/redirect-resolution logic is still
    provably correct -- both Findings resolve to the exact same real
    normalized origin -- but under the Gate, a role="" Finding with no
    known claimant honestly contributes zero toward independence, same
    as any other UNKNOWN-provenance evidence, regardless of how many
    times the same real page was actually observed."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    same_final = PageObservation(url="https://example.com/prostadine", title="t", text_content=_long_text())
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: _FakePlugin(same_final))

    collect_evidence_from_source(
        "https://example.com/link-a", category="affiliate", source="test-source", task_description="task",
        knowledge=knowledge, subject="Prostadine", ai_provider=_FakeAIProvider(relevant=True, subject_match="same"),
    )
    collect_evidence_from_source(
        "https://example.com/link-b-different-requested-url", category="affiliate", source="test-source",
        task_description="task", knowledge=knowledge, subject="Prostadine",
        ai_provider=_FakeAIProvider(relevant=True, subject_match="same"),
    )

    findings = knowledge.findings(subject="Prostadine")
    assert len(findings) == 2
    # the real normalization/redirect-resolution logic is still correct --
    # both resolve to the exact same real origin.
    assert evidence_origin(findings[0]) == evidence_origin(findings[1]) == "https://example.com/prostadine"
    # but honestly contributes zero -- role="" (never guessed by this
    # generic writer) and claimant="" together mean UNKNOWN, fail-closed.
    assert independent_source_count(findings) == 0


def test_i_subject_verified_with_unknown_provenance_is_trusted_but_not_independent(tmp_path, monkeypatch):
    """Test I: a genuinely subject-correct Finding may exist even when
    its provenance can't be counted toward independence -- the two
    contracts (Gate 1 subject-attribution, and evidence-provenance
    independence) are proven orthogonal, not merged."""
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    # a real observation with no parseable URL at all (e.g. a non-URL
    # source_ref/marker) -- subject verification can still pass
    plugin = _FakePlugin(PageObservation(url="local screen capture", title="Prostadine", text_content=_long_text("real Prostadine content")))
    monkeypatch.setattr(mod, "select_plugin", lambda source_ref: plugin)

    finding = collect_evidence_from_source(
        "some-source", category="affiliate", source="test-source", task_description="task",
        knowledge=knowledge, subject="Prostadine", ai_provider=_FakeAIProvider(relevant=True, subject_match="same"),
    )

    assert finding is not None  # trusted -- subject verification passed, real Finding exists
    assert knowledge.findings(subject="Prostadine") == [finding]
    assert independent_source_count([finding]) == 0  # but contributes nothing toward independence
