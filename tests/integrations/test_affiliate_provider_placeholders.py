import pytest

from atlas.integrations.affiliate_provider_placeholders import (
    AliExpressAffiliateProvider,
    AmazonAssociatesProvider,
    CJProvider,
    ImpactProvider,
    ShareASaleProvider,
)
from atlas.integrations.base import OpportunityProvider

ALL_PLACEHOLDERS = [
    (AmazonAssociatesProvider, "amazon_associates"),
    (AliExpressAffiliateProvider, "aliexpress_affiliate"),
    (CJProvider, "cj"),
    (ImpactProvider, "impact"),
    (ShareASaleProvider, "shareasale"),
]


@pytest.mark.parametrize("provider_class,expected_name", ALL_PLACEHOLDERS)
def test_placeholder_satisfies_the_opportunity_provider_protocol(provider_class, expected_name):
    assert isinstance(provider_class(), OpportunityProvider)


@pytest.mark.parametrize("provider_class,expected_name", ALL_PLACEHOLDERS)
def test_placeholder_declares_its_real_name_and_the_affiliate_category(provider_class, expected_name):
    provider = provider_class()
    assert provider.name == expected_name
    assert provider.category == "affiliate"


@pytest.mark.parametrize("provider_class,expected_name", ALL_PLACEHOLDERS)
def test_placeholder_fetch_opportunities_always_returns_none_never_a_fabricated_result(provider_class, expected_name):
    # No real API integration exists for any of these -- None is the
    # only honest answer, never an empty list (which would read as "we
    # checked and found nothing") and never a fabricated opportunity.
    assert provider_class().fetch_opportunities() is None


def test_every_placeholder_has_a_distinct_name():
    names = [provider_class().name for provider_class, _ in ALL_PLACEHOLDERS]
    assert len(names) == len(set(names))
