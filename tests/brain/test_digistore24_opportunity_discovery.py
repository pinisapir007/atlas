import pytest

from atlas.brain.digistore24_opportunity_discovery import (
    Digistore24SignalProvider,
    discover_and_rank_digistore24_opportunities,
    score_marketplace_entry,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.integrations.base import Opportunity, OpportunityProvider
from atlas.integrations.digistore24 import Digistore24APIError


class _FakeStore:
    """A minimal in-memory BrainStore stand-in -- same pattern used
    throughout this codebase's tests to isolate from real .atlas/ files."""

    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeProvider:
    """A duck-typed stand-in for Digistore24Provider -- only implements
    the two methods discover_and_rank_digistore24_opportunities() calls,
    so tests never need to mock urllib.request.urlopen."""

    name = "digistore24"
    category = "affiliate"

    def __init__(self, list_response, entry_responses=None):
        self._list_response = list_response
        self._entry_responses = entry_responses or {}

    def list_marketplace_entries(self):
        return self._list_response

    def get_marketplace_entry(self, entry_id):
        response = self._entry_responses.get(entry_id)
        if isinstance(response, Exception):
            raise response
        return response


def test_score_returns_none_when_no_profit_fields_present():
    assert score_marketplace_entry({"product_category": "health"}) is None


def test_score_returns_none_for_a_non_dict_entry():
    assert score_marketplace_entry(None) is None


def test_score_uses_real_profit_fields_when_present():
    score = score_marketplace_entry({"stats_affiliate_profit_sale": 10.0, "stats_affiliate_profit_visitor": 2.0})
    assert score == 6.0  # average of the two real profit fields, no competition/risk data to modulate by


def test_score_is_dampened_by_real_competition():
    low_competition = score_marketplace_entry({"stats_affiliate_profit_sale": 10.0, "stats_count_affiliates_with_sales": 1})
    high_competition = score_marketplace_entry({"stats_affiliate_profit_sale": 10.0, "stats_count_affiliates_with_sales": 100})
    assert low_competition > high_competition


def test_score_is_reduced_by_real_cancel_rate():
    no_cancels = score_marketplace_entry({"stats_affiliate_profit_sale": 10.0})
    with_cancels = score_marketplace_entry({"stats_affiliate_profit_sale": 10.0, "stats_cancel_rate": 0.5})
    assert with_cancels == pytest.approx(no_cancels * 0.5)


def test_discover_returns_empty_list_when_no_credential_configured():
    provider = _FakeProvider(list_response=None)
    assert discover_and_rank_digistore24_opportunities(provider) == []


def test_discover_gracefully_handles_the_real_confirmed_empty_marketplace_response():
    # The real, live-confirmed shape from this account: result=success,
    # count=0, entries=[] -- Digistore24's own documented vendor-scoping
    # correctly applying to an affiliate-only account. Not an error.
    provider = _FakeProvider(list_response={"result": "success", "count": 0, "entries": []})
    knowledge = KnowledgeBase(store=_FakeStore())

    results = discover_and_rank_digistore24_opportunities(provider, knowledge)

    assert results == []
    assert knowledge.findings() == []  # never fabricates a placeholder opportunity


def test_discover_handles_the_data_nested_envelope_shape_too():
    provider = _FakeProvider(list_response={"result": "success", "data": {"entries": []}})
    assert discover_and_rank_digistore24_opportunities(provider) == []


def test_discover_enriches_scores_and_ranks_real_entries():
    provider = _FakeProvider(
        list_response={"result": "success", "count": 2, "entries": [{"id": 1}, {"id": 2}]},
        entry_responses={
            "1": {"result": "success", "data": {"headline": "Low profit product", "product_category": "health", "stats_affiliate_profit_sale": 2.0}},
            "2": {"result": "success", "data": {"headline": "High profit product", "product_category": "fitness", "stats_affiliate_profit_sale": 20.0}},
        },
    )
    knowledge = KnowledgeBase(store=_FakeStore())

    results = discover_and_rank_digistore24_opportunities(provider, knowledge)

    assert [r["entry_id"] for r in results] == ["2", "1"]  # ranked descending by real score
    assert results[0]["score"] == 20.0
    findings = knowledge.findings()
    assert len(findings) == 2
    assert {f.subject for f in findings} == {"Low profit product", "High profit product"}
    assert all(f.provider == "digistore24" for f in findings)


def test_discover_skips_an_entry_whose_enrichment_call_fails_without_aborting_the_rest():
    provider = _FakeProvider(
        list_response={"result": "success", "count": 2, "entries": [{"id": 1}, {"id": 2}]},
        entry_responses={
            "1": Digistore24APIError("permission denied for entry 1"),
            "2": {"result": "success", "data": {"headline": "Real product", "stats_affiliate_profit_sale": 5.0}},
        },
    )

    results = discover_and_rank_digistore24_opportunities(provider)

    by_id = {r["entry_id"]: r for r in results}
    assert by_id["1"]["error"] == "permission denied for entry 1"
    assert by_id["1"]["score"] is None
    assert by_id["2"]["score"] == 5.0


def test_discover_skips_entries_with_no_real_id():
    provider = _FakeProvider(list_response={"result": "success", "entries": [{"headline": "no id field"}]})
    assert discover_and_rank_digistore24_opportunities(provider) == []


def test_digistore24_signal_provider_satisfies_the_opportunity_provider_protocol():
    assert isinstance(Digistore24SignalProvider(), OpportunityProvider)


def test_digistore24_signal_provider_fetch_opportunities_returns_none_with_no_credential():
    provider = Digistore24SignalProvider(_FakeProvider(list_response=None))
    assert provider.fetch_opportunities() is None


def test_digistore24_signal_provider_fetch_opportunities_returns_normalized_opportunities():
    fake_provider = _FakeProvider(
        list_response={"result": "success", "count": 1, "entries": [{"id": 1}]},
        entry_responses={"1": {"result": "success", "data": {"headline": "Real product", "product_category": "health", "stats_affiliate_profit_sale": 10.0}}},
    )
    signal_provider = Digistore24SignalProvider(fake_provider)

    opportunities = signal_provider.fetch_opportunities()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert isinstance(opp, Opportunity)
    assert opp.provider == "digistore24"
    assert opp.external_id == "1"
    assert opp.title == "Real product"
    assert opp.category == "health"
    assert opp.score == 10.0
    assert opp.error is None


def test_digistore24_signal_provider_fetch_opportunities_surfaces_a_per_entry_error():
    fake_provider = _FakeProvider(
        list_response={"result": "success", "count": 1, "entries": [{"id": 1}]},
        entry_responses={"1": Digistore24APIError("permission denied")},
    )
    signal_provider = Digistore24SignalProvider(fake_provider)

    opportunities = signal_provider.fetch_opportunities()

    assert len(opportunities) == 1
    assert opportunities[0].error == "permission denied"
    assert opportunities[0].score is None
