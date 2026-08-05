"""Integration tests for ATLAS Intelligence Engine V1 — deliberately
using the REAL provider classes (FindingsMarketIntelligenceProvider and
all four real placeholder classes) wired through the REAL
collect_intelligence() engine, not the lightweight duck-typed fakes
test_intelligence_engine.py's unit tests use. Every store is still
isolated (_FakeStore / tmp_path-backed real KnowledgeBase) so nothing
here ever touches this project's real .atlas/ state.
"""

from atlas.brain.intelligence_engine import _default_providers, collect_intelligence
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.time_service import TimeService


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_real_findings_flow_through_the_full_real_pipeline_with_real_placeholders(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    knowledge.save_finding(Finding(source="research", category="affiliate", description="real evidence", evidence="https://example.com/1", subject="KetoDNA", market="US"))
    knowledge.save_finding(Finding(source="research", category="digital_product", description="more real evidence", subject="Widget"))

    index = IntelligenceIndex(store=_FakeStore())
    providers = _default_providers(knowledge, TimeService())

    result = collect_intelligence(providers=providers, index=index)

    # The real market provider contributed both real Findings...
    assert result["provider_status"]["findings_market_intelligence"]["count"] == 2
    market_items = [i for i in result["intelligence"] if i.domain == "market"]
    assert {i.subject for i in market_items} == {"KetoDNA", "Widget"}

    # ...and every real placeholder correctly reported unavailable,
    # without affecting the market provider's real results at all.
    for placeholder_name in ("human_behavior_intelligence", "competitor_intelligence", "product_intelligence", "economic_intelligence"):
        assert result["provider_status"][placeholder_name] == {"count": 0, "error": "not available (no real data source configured, or not yet implemented)"}

    # And the index is queryable afterward without any new collection.
    assert index.count() == 2
    assert len(index.by_domain("market")) == 2
    assert index.by_domain("competitor") == []


def test_collect_intelligence_gracefully_handles_a_real_empty_knowledge_base(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")  # real, genuinely empty
    index = IntelligenceIndex(store=_FakeStore())

    result = collect_intelligence(providers=_default_providers(knowledge, TimeService()), index=index)

    assert result["intelligence"] == []
    assert result["provider_status"]["findings_market_intelligence"] == {"count": 0, "error": None}
    assert index.count() == 0


def test_a_second_real_collection_reflects_new_real_evidence_and_drops_nothing_stale(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    index = IntelligenceIndex(store=_FakeStore())

    knowledge.save_finding(Finding(source="research", category="affiliate", description="first", subject="A"))
    collect_intelligence(providers=_default_providers(knowledge, TimeService()), index=index)
    assert index.count() == 1

    knowledge.save_finding(Finding(source="research", category="affiliate", description="second", subject="B"))
    collect_intelligence(providers=_default_providers(knowledge, TimeService()), index=index)

    assert index.count() == 2
    assert {i.subject for i in index.all_intelligence()} == {"A", "B"}


def test_intelligence_engine_never_writes_to_knowledge_base(tmp_path):
    # Collection is read-only end to end -- no real Finding is ever
    # created as a side effect of running this engine.
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    knowledge.save_finding(Finding(source="research", category="affiliate", description="real", subject="A"))
    findings_before = len(knowledge.findings())

    collect_intelligence(providers=_default_providers(knowledge, TimeService()), index=IntelligenceIndex(store=_FakeStore()))

    assert len(knowledge.findings()) == findings_before
