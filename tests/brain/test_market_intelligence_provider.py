from datetime import datetime, timezone

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.market_intelligence_provider import FindingsMarketIntelligenceProvider
from atlas.brain.models import Finding
from atlas.brain.time_service import TimeService
from atlas.integrations.base import Intelligence, IntelligenceProvider


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _knowledge():
    return KnowledgeBase(store=_FakeStore())


_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_satisfies_the_intelligence_provider_protocol():
    assert isinstance(FindingsMarketIntelligenceProvider(_knowledge()), IntelligenceProvider)


def test_declares_the_real_name_and_market_domain():
    provider = FindingsMarketIntelligenceProvider(_knowledge())
    assert provider.name == "findings_market_intelligence"
    assert provider.domain == "market"


def test_returns_a_real_empty_list_never_none_with_zero_findings():
    # Always "available" -- a local file, no credential needed -- so a
    # real check that finds nothing is [], not None.
    provider = FindingsMarketIntelligenceProvider(_knowledge())
    result = provider.fetch_intelligence()
    assert result == []


def test_normalizes_a_real_finding_into_a_real_intelligence_object():
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="research", category="affiliate", description="real evidence", evidence="https://example.com/1", subject="KetoDNA", market="US"))
    provider = FindingsMarketIntelligenceProvider(knowledge, TimeService(clock=lambda: _NOW))

    result = provider.fetch_intelligence()

    assert len(result) == 1
    item = result[0]
    assert isinstance(item, Intelligence)
    assert item.provider == "findings_market_intelligence"
    assert item.domain == "market"
    assert item.subject == "KetoDNA"
    assert item.summary == "real evidence"
    assert item.source == "research"
    assert item.evidence == "https://example.com/1"
    assert item.market == "US"
    assert item.collected_at == _NOW.isoformat()
    assert item.error is None


def test_falls_back_to_category_when_a_finding_has_no_real_subject():
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="research", category="affiliate", description="category-general evidence"))
    provider = FindingsMarketIntelligenceProvider(knowledge)

    result = provider.fetch_intelligence()

    assert result[0].subject == "affiliate"


def test_every_real_finding_is_represented():
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="research", category="affiliate", description="one"))
    knowledge.save_finding(Finding(source="research", category="digital_product", description="two"))
    provider = FindingsMarketIntelligenceProvider(knowledge)

    result = provider.fetch_intelligence()

    assert len(result) == 2
    assert {i.summary for i in result} == {"one", "two"}


def test_raw_carries_the_real_finding_id_for_traceability():
    knowledge = _knowledge()
    knowledge.save_finding(Finding(source="research", category="affiliate", description="real evidence"))
    provider = FindingsMarketIntelligenceProvider(knowledge)

    item = provider.fetch_intelligence()[0]

    assert "finding_id" in item.raw
    assert item.raw["category"] == "affiliate"


def test_default_construction_works_without_explicit_dependencies():
    # No knowledge/time_service injected -- must fall back to real
    # instances and never raise.
    provider = FindingsMarketIntelligenceProvider()
    result = provider.fetch_intelligence()
    assert isinstance(result, list)
