from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.opportunity_discovery_engine import discover_opportunities
from atlas.integrations.base import Opportunity


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeOpportunityProvider:
    """A minimal, duck-typed OpportunityProvider stand-in -- name,
    category, fetch_opportunities() -- used to test the engine's
    aggregation and fault-isolation without touching any real provider."""

    def __init__(self, name, category="affiliate", opportunities=None, raises=None):
        self.name = name
        self.category = category
        self._opportunities = opportunities
        self._raises = raises

    def fetch_opportunities(self):
        if self._raises is not None:
            raise self._raises
        return self._opportunities


def test_discover_with_no_providers_returns_empty_and_no_error():
    result = discover_opportunities(providers=[])
    assert result == {"opportunities": [], "provider_status": {}}


def test_a_provider_with_no_credential_does_not_stop_other_providers():
    broken = _FakeOpportunityProvider("no_credential_provider", opportunities=None)
    working = _FakeOpportunityProvider(
        "working_provider", opportunities=[Opportunity(provider="working_provider", external_id="1", title="Real product", score=5.0, raw={"headline": "Real product"})]
    )

    result = discover_opportunities(providers=[broken, working])

    assert result["provider_status"]["no_credential_provider"] == {"count": 0, "error": "not available (no credential configured, or not yet implemented)"}
    assert result["provider_status"]["working_provider"]["count"] == 1
    assert len(result["opportunities"]) == 1
    assert result["opportunities"][0].provider == "working_provider"


def test_a_provider_that_raises_does_not_stop_other_providers():
    class _RealFailure(Exception):
        pass

    broken = _FakeOpportunityProvider("crashing_provider", raises=_RealFailure("real network error"))
    working = _FakeOpportunityProvider(
        "working_provider", opportunities=[Opportunity(provider="working_provider", external_id="1", title="Still works", score=3.0, raw={"headline": "Still works"})]
    )

    result = discover_opportunities(providers=[broken, working])

    assert result["provider_status"]["crashing_provider"] == {"count": 0, "error": "real network error"}
    assert result["provider_status"]["working_provider"]["count"] == 1
    assert len(result["opportunities"]) == 1


def test_a_provider_with_zero_real_results_does_not_stop_others_and_is_reported_honestly():
    empty = _FakeOpportunityProvider("empty_provider", opportunities=[])
    working = _FakeOpportunityProvider(
        "working_provider", opportunities=[Opportunity(provider="working_provider", external_id="1", title="x", score=1.0, raw={"headline": "x"})]
    )

    result = discover_opportunities(providers=[empty, working])

    assert result["provider_status"]["empty_provider"] == {"count": 0, "error": None}
    assert len(result["opportunities"]) == 1


def test_a_placeholder_provider_returning_none_does_not_stop_a_real_one():
    # Exactly the real shape of a placeholder (Amazon/AliExpress/CJ/
    # Impact/ShareASale): always None, never fatal to other providers.
    placeholder = _FakeOpportunityProvider("amazon_associates", opportunities=None)
    real = _FakeOpportunityProvider(
        "digistore24", opportunities=[Opportunity(provider="digistore24", external_id="1", title="real entry", score=7.0, raw={"headline": "real entry"})]
    )

    result = discover_opportunities(providers=[placeholder, real])

    assert result["provider_status"]["amazon_associates"]["count"] == 0
    assert result["provider_status"]["digistore24"]["count"] == 1
    assert len(result["opportunities"]) == 1


def test_results_are_ranked_across_providers_by_real_score_descending():
    provider_a = _FakeOpportunityProvider("provider_a", opportunities=[Opportunity(provider="provider_a", external_id="a1", title="low", score=2.0, raw={"headline": "low"})])
    provider_b = _FakeOpportunityProvider("provider_b", opportunities=[Opportunity(provider="provider_b", external_id="b1", title="high", score=9.0, raw={"headline": "high"})])

    result = discover_opportunities(providers=[provider_a, provider_b])

    assert [o.external_id for o in result["opportunities"]] == ["b1", "a1"]


def test_unscored_results_rank_below_scored_ones_regardless_of_provider():
    provider = _FakeOpportunityProvider(
        "provider_x",
        opportunities=[
            Opportunity(provider="provider_x", external_id="unscored", title="no real profit data", score=None, raw={"headline": "no real profit data"}),
            Opportunity(provider="provider_x", external_id="scored", title="has real data", score=1.0, raw={"headline": "has real data"}),
        ],
    )

    result = discover_opportunities(providers=[provider])

    assert [o.external_id for o in result["opportunities"]] == ["scored", "unscored"]


def test_real_findings_are_saved_per_provider_when_knowledge_is_given():
    provider = _FakeOpportunityProvider(
        "provider_x",
        category="affiliate",
        opportunities=[Opportunity(provider="provider_x", external_id="1", title="Real product", category="health", score=4.0, raw={"headline": "Real product", "product_category": "health"})],
    )
    knowledge = KnowledgeBase(store=_FakeStore())

    discover_opportunities(providers=[provider], knowledge=knowledge)

    findings = knowledge.findings()
    assert len(findings) == 1
    assert findings[0].provider == "provider_x"
    assert findings[0].category == "health"
    assert findings[0].subject == "Real product"


def test_no_finding_saved_for_a_result_with_no_real_raw_data():
    provider = _FakeOpportunityProvider(
        "provider_x", opportunities=[Opportunity(provider="provider_x", external_id="1", title="1", score=None, raw={}, error="permission denied")]
    )
    knowledge = KnowledgeBase(store=_FakeStore())

    discover_opportunities(providers=[provider], knowledge=knowledge)

    assert knowledge.findings() == []


def test_no_finding_saved_for_a_result_with_a_real_error():
    provider = _FakeOpportunityProvider(
        "provider_x",
        opportunities=[Opportunity(provider="provider_x", external_id="1", title="1", score=None, raw={"headline": "x"}, error="permission denied")],
    )
    knowledge = KnowledgeBase(store=_FakeStore())

    discover_opportunities(providers=[provider], knowledge=knowledge)

    assert knowledge.findings() == []  # a real per-entry error is surfaced in provider results, never silently turned into a Finding


def test_default_providers_registers_digistore24_and_all_five_placeholders(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    result = discover_opportunities()  # real default provider list -- no explicit providers given

    expected_providers = {"digistore24", "amazon_associates", "aliexpress_affiliate", "cj", "impact", "shareasale"}
    assert set(result["provider_status"]) == expected_providers
    for name, status in result["provider_status"].items():
        assert status["count"] == 0  # no real credential for any of them in this test run
    assert result["opportunities"] == []
