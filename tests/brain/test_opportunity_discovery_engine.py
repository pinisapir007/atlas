from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.opportunity_discovery_engine import discover_opportunities


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeSignalProvider:
    """A minimal, duck-typed MarketSignalProvider stand-in -- name,
    category, fetch_signals() -- used to test the engine's aggregation
    and fault-isolation without touching any real provider."""

    def __init__(self, name, category="affiliate", signals=None, raises=None):
        self.name = name
        self.category = category
        self._signals = signals
        self._raises = raises

    def fetch_signals(self):
        if self._raises is not None:
            raise self._raises
        return self._signals


def test_discover_with_no_providers_returns_empty_and_no_error():
    result = discover_opportunities(providers=[])
    assert result == {"opportunities": [], "provider_status": {}}


def test_a_provider_with_no_credential_does_not_stop_other_providers():
    broken = _FakeSignalProvider("no_credential_provider", signals=None)
    working = _FakeSignalProvider("working_provider", signals=[{"id": "1", "score": 5.0, "data": {"headline": "Real product"}, "error": None}])

    result = discover_opportunities(providers=[broken, working])

    assert result["provider_status"]["no_credential_provider"] == {"count": 0, "error": "no credential configured"}
    assert result["provider_status"]["working_provider"]["count"] == 1
    assert len(result["opportunities"]) == 1
    assert result["opportunities"][0]["provider"] == "working_provider"


def test_a_provider_that_raises_does_not_stop_other_providers():
    class _RealFailure(Exception):
        pass

    broken = _FakeSignalProvider("crashing_provider", raises=_RealFailure("real network error"))
    working = _FakeSignalProvider("working_provider", signals=[{"id": "1", "score": 3.0, "data": {"headline": "Still works"}, "error": None}])

    result = discover_opportunities(providers=[broken, working])

    assert result["provider_status"]["crashing_provider"] == {"count": 0, "error": "real network error"}
    assert result["provider_status"]["working_provider"]["count"] == 1
    assert len(result["opportunities"]) == 1


def test_a_provider_with_zero_real_results_does_not_stop_others_and_is_reported_honestly():
    empty = _FakeSignalProvider("empty_provider", signals=[])
    working = _FakeSignalProvider("working_provider", signals=[{"id": "1", "score": 1.0, "data": {"headline": "x"}, "error": None}])

    result = discover_opportunities(providers=[empty, working])

    assert result["provider_status"]["empty_provider"] == {"count": 0, "error": None}
    assert len(result["opportunities"]) == 1


def test_results_are_ranked_across_providers_by_real_score_descending():
    provider_a = _FakeSignalProvider("provider_a", signals=[{"id": "a1", "score": 2.0, "data": {"headline": "low"}, "error": None}])
    provider_b = _FakeSignalProvider("provider_b", signals=[{"id": "b1", "score": 9.0, "data": {"headline": "high"}, "error": None}])

    result = discover_opportunities(providers=[provider_a, provider_b])

    assert [o["id"] for o in result["opportunities"]] == ["b1", "a1"]


def test_unscored_results_rank_below_scored_ones_regardless_of_provider():
    provider = _FakeSignalProvider(
        "provider_x",
        signals=[
            {"id": "unscored", "score": None, "data": {"headline": "no real profit data"}, "error": None},
            {"id": "scored", "score": 1.0, "data": {"headline": "has real data"}, "error": None},
        ],
    )

    result = discover_opportunities(providers=[provider])

    assert [o["id"] for o in result["opportunities"]] == ["scored", "unscored"]


def test_real_findings_are_saved_per_provider_when_knowledge_is_given():
    provider = _FakeSignalProvider(
        "provider_x", category="affiliate", signals=[{"id": "1", "score": 4.0, "data": {"headline": "Real product", "product_category": "health"}, "error": None}]
    )
    knowledge = KnowledgeBase(store=_FakeStore())

    discover_opportunities(providers=[provider], knowledge=knowledge)

    findings = knowledge.findings()
    assert len(findings) == 1
    assert findings[0].provider == "provider_x"
    assert findings[0].category == "health"
    assert findings[0].subject == "Real product"


def test_no_findings_saved_for_a_result_with_no_real_data():
    provider = _FakeSignalProvider("provider_x", signals=[{"id": "1", "score": None, "data": {}, "error": "permission denied"}])
    knowledge = KnowledgeBase(store=_FakeStore())

    discover_opportunities(providers=[provider], knowledge=knowledge)

    assert knowledge.findings() == []


def test_default_providers_includes_digistore24_and_handles_no_credential_gracefully(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    result = discover_opportunities()  # real default provider list, no credential configured in this test run
    assert result["provider_status"]["digistore24"] == {"count": 0, "error": "no credential configured"}
    assert result["opportunities"] == []
