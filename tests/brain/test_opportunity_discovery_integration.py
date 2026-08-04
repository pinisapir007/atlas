"""Integration tests for the multi-provider Opportunity Discovery
pipeline (2026-08-05) — deliberately using the REAL provider classes
(Digistore24SignalProvider, the five real placeholder classes) wired
through the REAL discover_opportunities() engine, unlike
test_opportunity_discovery_engine.py's unit tests, which exercise the
engine against lightweight duck-typed fakes. The only fake here is the
one thing that has to be: the underlying HTTP-calling Digistore24Provider,
stood in for so no real network call happens — everything above that
(scoring, normalization into Opportunity, the engine's merge/dedupe/
rank/Finding-saving) is the real, unmodified code path.
"""

from atlas.brain.digistore24_opportunity_discovery import Digistore24SignalProvider
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.opportunity_discovery_engine import _default_providers, discover_opportunities
from atlas.integrations.affiliate_provider_placeholders import (
    AliExpressAffiliateProvider,
    AmazonAssociatesProvider,
    CJProvider,
    ImpactProvider,
    ShareASaleProvider,
)
from atlas.integrations.digistore24 import Digistore24APIError


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeDigistore24Provider:
    """Stands in for the real, network-calling Digistore24Provider --
    same duck-typed shape test_digistore24_opportunity_discovery.py
    already established. Digistore24SignalProvider itself, its scoring,
    and every layer above this fake are entirely real and unmodified."""

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


def _real_providers_with_fake_digistore24(fake_digistore24):
    """The real default provider set, with only the innermost network
    call swapped for a fake -- Digistore24SignalProvider,
    AmazonAssociatesProvider, etc. are all the genuine, unmodified
    classes."""
    return [
        Digistore24SignalProvider(fake_digistore24),
        AmazonAssociatesProvider(),
        AliExpressAffiliateProvider(),
        CJProvider(),
        ImpactProvider(),
        ShareASaleProvider(),
    ]


def test_default_providers_is_the_real_six_provider_list_used_by_the_engine():
    # Proves _default_providers() (what discover_opportunities() uses
    # when the caller supplies nothing) really does construct the real
    # Digistore24SignalProvider plus the real five placeholders -- not
    # just that some test double claiming those names does.
    providers = _default_providers()
    names = {p.name for p in providers}
    assert names == {"digistore24", "amazon_associates", "aliexpress_affiliate", "cj", "impact", "shareasale"}
    assert isinstance(providers[0], Digistore24SignalProvider)


def test_real_digistore24_result_flows_through_the_full_real_pipeline_with_real_placeholders():
    fake_digistore24 = _FakeDigistore24Provider(
        list_response={"result": "success", "count": 1, "entries": [{"id": 1}]},
        entry_responses={
            "1": {
                "result": "success",
                "data": {"headline": "Real KetoDNA-style product", "product_category": "health", "stats_affiliate_profit_sale": 12.0},
            }
        },
    )
    knowledge = KnowledgeBase(store=_FakeStore())

    result = discover_opportunities(providers=_real_providers_with_fake_digistore24(fake_digistore24), knowledge=knowledge)

    # The one real provider contributed its real, scored opportunity...
    assert result["provider_status"]["digistore24"] == {"count": 1, "error": None}
    assert len(result["opportunities"]) == 1
    opp = result["opportunities"][0]
    assert opp.provider == "digistore24"
    assert opp.title == "Real KetoDNA-style product"
    assert opp.score == 12.0

    # ...and every real placeholder correctly reported unavailable,
    # without affecting Digistore24's real result at all.
    for placeholder_name in ("amazon_associates", "aliexpress_affiliate", "cj", "impact", "shareasale"):
        assert result["provider_status"][placeholder_name]["count"] == 0
        assert "not available" in result["provider_status"][placeholder_name]["error"]

    # And a real Finding was recorded end to end.
    findings = knowledge.findings()
    assert len(findings) == 1
    assert findings[0].provider == "digistore24"
    assert findings[0].category == "health"


def test_a_real_digistore24_api_failure_does_not_prevent_placeholder_reporting():
    # The real per-entry Digistore24APIError path, flowing all the way
    # through the real engine, alongside real (inert) placeholders.
    fake_digistore24 = _FakeDigistore24Provider(
        list_response={"result": "success", "count": 1, "entries": [{"id": 1}]},
        entry_responses={"1": Digistore24APIError("permission denied")},
    )

    result = discover_opportunities(providers=_real_providers_with_fake_digistore24(fake_digistore24))

    digistore24_opportunity = result["opportunities"][0]
    assert digistore24_opportunity.error == "permission denied"
    assert digistore24_opportunity.score is None
    assert result["provider_status"]["amazon_associates"]["count"] == 0  # still ran, still reported, unaffected


def test_real_engine_gracefully_handles_zero_real_data_from_every_real_and_placeholder_provider():
    # The exact real, live-confirmed state from earlier work: a real
    # account with zero marketplace entries, plus five real, honestly
    # unimplemented placeholders. The engine must complete cleanly.
    fake_digistore24 = _FakeDigistore24Provider(list_response={"result": "success", "count": 0, "entries": []})

    result = discover_opportunities(providers=_real_providers_with_fake_digistore24(fake_digistore24))

    assert result["opportunities"] == []
    assert all(status["count"] == 0 for status in result["provider_status"].values())


def test_real_pipeline_deduplicates_a_real_repeated_digistore24_entry():
    # A real provider bug (the same entry_id listed twice by
    # listMarketplaceEntries) flowing through the real dedup step.
    fake_digistore24 = _FakeDigistore24Provider(
        list_response={"result": "success", "count": 2, "entries": [{"id": 1}, {"id": 1}]},
        entry_responses={"1": {"result": "success", "data": {"headline": "Real product", "stats_affiliate_profit_sale": 5.0}}},
    )

    result = discover_opportunities(providers=_real_providers_with_fake_digistore24(fake_digistore24))

    assert len(result["opportunities"]) == 1
    assert result["provider_status"]["digistore24"]["count"] == 2  # the provider really did return 2 raw entries
