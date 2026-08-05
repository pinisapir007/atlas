from atlas.brain.intelligence_engine import _default_providers, collect_intelligence
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.market_intelligence_provider import FindingsMarketIntelligenceProvider
from atlas.integrations.base import Intelligence


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _index():
    return IntelligenceIndex(store=_FakeStore())


class _FakeIntelligenceProvider:
    """A minimal, duck-typed IntelligenceProvider stand-in -- name,
    domain, fetch_intelligence() -- used to test the engine's
    aggregation and fault-isolation without touching any real provider."""

    def __init__(self, name, domain="market", items=None, raises=None):
        self.name = name
        self.domain = domain
        self._items = items
        self._raises = raises

    def fetch_intelligence(self):
        if self._raises is not None:
            raise self._raises
        return self._items


def test_default_providers_is_the_real_market_provider_plus_four_placeholders():
    providers = _default_providers()
    names = {p.name for p in providers}
    assert names == {"findings_market_intelligence", "human_behavior_intelligence", "competitor_intelligence", "product_intelligence", "economic_intelligence"}
    assert isinstance(providers[0], FindingsMarketIntelligenceProvider)


def test_collect_with_no_providers_returns_empty_and_replaces_the_index_empty():
    index = _index()
    index.replace_index([Intelligence(provider="stale", domain="market", subject="old", summary="stale data")])

    result = collect_intelligence(providers=[], index=index)

    assert result == {"intelligence": [], "provider_status": {}}
    assert index.count() == 0  # the stale entry is gone -- full replacement, not a no-op


def test_a_provider_with_no_real_source_does_not_stop_other_providers():
    unavailable = _FakeIntelligenceProvider("unavailable_provider", items=None)
    working = _FakeIntelligenceProvider("working_provider", items=[Intelligence(provider="working_provider", domain="market", subject="Widget", summary="real")])

    result = collect_intelligence(providers=[unavailable, working], index=_index())

    assert result["provider_status"]["unavailable_provider"] == {"count": 0, "error": "not available (no real data source configured, or not yet implemented)"}
    assert result["provider_status"]["working_provider"]["count"] == 1
    assert len(result["intelligence"]) == 1


def test_a_provider_that_raises_does_not_stop_other_providers():
    class _RealFailure(Exception):
        pass

    broken = _FakeIntelligenceProvider("crashing_provider", raises=_RealFailure("real error"))
    working = _FakeIntelligenceProvider("working_provider", items=[Intelligence(provider="working_provider", domain="market", subject="Widget", summary="real")])

    result = collect_intelligence(providers=[broken, working], index=_index())

    assert result["provider_status"]["crashing_provider"] == {"count": 0, "error": "real error"}
    assert result["provider_status"]["working_provider"]["count"] == 1


def test_a_provider_with_zero_real_items_does_not_stop_others():
    empty = _FakeIntelligenceProvider("empty_provider", items=[])
    working = _FakeIntelligenceProvider("working_provider", items=[Intelligence(provider="working_provider", domain="market", subject="Widget", summary="real")])

    result = collect_intelligence(providers=[empty, working], index=_index())

    assert result["provider_status"]["empty_provider"] == {"count": 0, "error": None}
    assert len(result["intelligence"]) == 1


def test_a_provider_returning_malformed_entries_does_not_corrupt_the_aggregate():
    malformed = _FakeIntelligenceProvider("malformed_provider", items=[{"not": "an Intelligence"}, None, "also not one"])
    working = _FakeIntelligenceProvider("working_provider", items=[Intelligence(provider="working_provider", domain="market", subject="Widget", summary="real")])

    result = collect_intelligence(providers=[malformed, working], index=_index())

    assert result["provider_status"]["malformed_provider"]["count"] == 0
    assert len(result["intelligence"]) == 1


def test_collected_intelligence_is_combined_across_multiple_domains():
    market = _FakeIntelligenceProvider("market_provider", domain="market", items=[Intelligence(provider="market_provider", domain="market", subject="Widget", summary="m")])
    competitor = _FakeIntelligenceProvider("competitor_provider", domain="competitor", items=[Intelligence(provider="competitor_provider", domain="competitor", subject="RivalCo", summary="c")])

    result = collect_intelligence(providers=[market, competitor], index=_index())

    domains = {i.domain for i in result["intelligence"]}
    assert domains == {"market", "competitor"}


def test_collect_replaces_the_index_with_the_current_real_result():
    index = _index()
    provider = _FakeIntelligenceProvider("provider_x", items=[Intelligence(provider="provider_x", domain="market", subject="Widget", summary="real")])

    collect_intelligence(providers=[provider], index=index)

    indexed = index.all_intelligence()
    assert len(indexed) == 1
    assert indexed[0].subject == "Widget"


def test_intelligence_engine_never_generates_opportunities_or_findings():
    # A structural guarantee this module honors: collect_intelligence()
    # never touches KnowledgeBase.save_finding() or anything Opportunity-
    # shaped -- verified by checking it accepts no such dependency and
    # its return shape carries no "opportunity"/"score"-style fields.
    provider = _FakeIntelligenceProvider("provider_x", items=[Intelligence(provider="provider_x", domain="market", subject="Widget", summary="real")])
    result = collect_intelligence(providers=[provider], index=_index())
    assert set(result) == {"intelligence", "provider_status"}


def test_collect_intelligence_works_with_real_default_providers_when_none_supplied():
    # providers=None (not passed) -> _default_providers() constructs the
    # real FindingsMarketIntelligenceProvider against the real, default
    # KnowledgeBase (read-only, harmless). `index` is still explicitly
    # isolated here so this test never writes to the real
    # .atlas/intelligence_index.json.
    result = collect_intelligence(index=_index())
    assert "findings_market_intelligence" in result["provider_status"]
