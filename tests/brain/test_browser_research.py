import pytest

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.brain.browser_research import DomainNotApprovedError, collect_evidence_from_url
from atlas.brain.decision_engine import decide
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.integrations.base import PageObservation


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeObserver:
    """The exact same role a real StagehandObserver/BrowserUseObserver
    implementation will play once one is chosen -- this test proves the
    entire integration (allowlist -> observe -> Finding -> KnowledgeBase
    -> Decision Engine) works correctly without depending on any real
    browser library existing yet."""

    name = "fake"

    def __init__(self, observation: PageObservation | None = None, error: Exception | None = None):
        self._observation = observation
        self._error = error
        self.calls: list[tuple[str, dict | None]] = []

    def observe(self, url: str, extract=None) -> PageObservation:
        self.calls.append((url, extract))
        if self._error is not None:
            raise self._error
        return self._observation


def _world(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)
    allowlist = BrowserAllowlist(store=_FakeStore())
    return knowledge, memory, kpis, allowlist


def test_domain_not_approved_is_refused_before_the_observer_is_ever_called(tmp_path):
    knowledge, memory, kpis, allowlist = _world(tmp_path)
    observer = _FakeObserver(observation=PageObservation(url="x", title="x", text_content="x"))

    with pytest.raises(DomainNotApprovedError):
        collect_evidence_from_url(
            "https://reddit.com/r/keto", category="affiliate", source="reddit",
            observer=observer, allowlist=allowlist, knowledge=knowledge,
        )

    assert observer.calls == []  # never even attempted -- allowlist checked first


def test_a_real_allowed_observation_produces_a_real_finding(tmp_path):
    knowledge, memory, kpis, allowlist = _world(tmp_path)
    allowlist.approve_domain("reddit.com")
    observation = PageObservation(
        url="https://reddit.com/r/keto/comments/123",
        title="Best keto snacks thread",
        text_content="Real thread content: people discussing real keto snack brands they trust.",
    )
    observer = _FakeObserver(observation=observation)

    finding = collect_evidence_from_url(
        "https://reddit.com/r/keto/comments/123", category="affiliate", source="reddit",
        observer=observer, allowlist=allowlist, knowledge=knowledge,
        subject="keto snacks", market="US",
    )

    assert finding.source == "reddit"
    assert finding.category == "affiliate"
    assert finding.evidence == "https://reddit.com/r/keto/comments/123"
    assert finding.subject == "keto snacks"
    assert finding.market == "US"
    assert "Real thread content" in finding.description
    # never inferred -- category/subject/market came only from the caller
    assert observer.calls == [("https://reddit.com/r/keto/comments/123", None)]


def test_the_finding_is_really_persisted_to_disk_not_just_in_memory(tmp_path):
    knowledge, memory, kpis, allowlist = _world(tmp_path)
    allowlist.approve_domain("reddit.com")
    observer = _FakeObserver(observation=PageObservation(url="u", title="t", text_content="real content"))

    collect_evidence_from_url(
        "https://reddit.com/x", category="affiliate", source="reddit",
        observer=observer, allowlist=allowlist, knowledge=knowledge,
    )

    # A genuinely new KnowledgeBase instance, same real file on disk --
    # proves this was actually written, not just held in memory.
    reloaded = KnowledgeBase(tmp_path / "knowledge.json")
    assert len(reloaded.findings()) == 1
    assert reloaded.findings()[0].evidence == "https://reddit.com/x"


def test_structured_extract_fields_are_included_in_the_finding_description(tmp_path):
    knowledge, memory, kpis, allowlist = _world(tmp_path)
    allowlist.approve_domain("digistore24.com")
    observation = PageObservation(
        url="https://digistore24.com/product/x", title="x", text_content="page body",
        structured_data={"commission": "75%", "price": "$47"},
    )
    observer = _FakeObserver(observation=observation)

    finding = collect_evidence_from_url(
        "https://digistore24.com/product/x", category="affiliate", source="digistore24",
        observer=observer, allowlist=allowlist, knowledge=knowledge,
        extract={"commission": "listed commission", "price": "listed price"},
    )

    assert "commission: 75%" in finding.description
    assert "price: $47" in finding.description
    assert observer.calls == [("https://digistore24.com/product/x", {"commission": "listed commission", "price": "listed price"})]


def test_a_real_observer_failure_never_records_a_fabricated_finding(tmp_path):
    knowledge, memory, kpis, allowlist = _world(tmp_path)
    allowlist.approve_domain("reddit.com")
    observer = _FakeObserver(error=RuntimeError("real timeout"))

    with pytest.raises(RuntimeError, match="real timeout"):
        collect_evidence_from_url(
            "https://reddit.com/x", category="affiliate", source="reddit",
            observer=observer, allowlist=allowlist, knowledge=knowledge,
        )

    assert knowledge.findings() == []


def test_end_to_end_a_browser_sourced_finding_is_real_evidence_the_decision_engine_already_consumes(tmp_path):
    """The core promise of this design: zero changes to decide() were
    made, and none are needed. Two real, browser-sourced Findings are
    enough on their own to cross decide()'s real MIN_INDEPENDENT_SOURCES
    evidence bar -- proven here by calling the real, unmodified
    decision_engine.decide() directly."""
    knowledge, memory, kpis, allowlist = _world(tmp_path)
    allowlist.approve_domain("reddit.com")
    allowlist.approve_domain("digistore24.com")

    collect_evidence_from_url(
        "https://reddit.com/r/keto", category="affiliate", source="reddit",
        observer=_FakeObserver(observation=PageObservation(url="u1", title="t1", text_content="real signal one")),
        allowlist=allowlist, knowledge=knowledge,
    )
    collect_evidence_from_url(
        "https://digistore24.com/marketplace", category="affiliate", source="digistore24",
        observer=_FakeObserver(observation=PageObservation(url="u2", title="t2", text_content="real signal two")),
        allowlist=allowlist, knowledge=knowledge,
    )

    decision = decide("affiliate", knowledge, memory, kpis)

    assert decision.verdict == "invest"
    assert len(decision.evidence_finding_ids) == 2
