import pytest

from atlas.integrations.base import IntelligenceProvider
from atlas.integrations.intelligence_provider_placeholders import (
    CompetitorIntelligenceProvider,
    EconomicIntelligenceProvider,
    HumanBehaviorIntelligenceProvider,
    ProductIntelligenceProvider,
)

ALL_PLACEHOLDERS = [
    (HumanBehaviorIntelligenceProvider, "human_behavior_intelligence", "human_behavior"),
    (CompetitorIntelligenceProvider, "competitor_intelligence", "competitor"),
    (ProductIntelligenceProvider, "product_intelligence", "product"),
    (EconomicIntelligenceProvider, "economic_intelligence", "economic"),
]


@pytest.mark.parametrize("provider_class,expected_name,expected_domain", ALL_PLACEHOLDERS)
def test_placeholder_satisfies_the_intelligence_provider_protocol(provider_class, expected_name, expected_domain):
    assert isinstance(provider_class(), IntelligenceProvider)


@pytest.mark.parametrize("provider_class,expected_name,expected_domain", ALL_PLACEHOLDERS)
def test_placeholder_declares_its_real_name_and_domain(provider_class, expected_name, expected_domain):
    provider = provider_class()
    assert provider.name == expected_name
    assert provider.domain == expected_domain


@pytest.mark.parametrize("provider_class,expected_name,expected_domain", ALL_PLACEHOLDERS)
def test_placeholder_fetch_intelligence_always_returns_none_never_a_fabricated_insight(provider_class, expected_name, expected_domain):
    assert provider_class().fetch_intelligence() is None


def test_every_placeholder_has_a_distinct_name_and_domain():
    names = [p().name for p, _, _ in ALL_PLACEHOLDERS]
    domains = [p().domain for p, _, _ in ALL_PLACEHOLDERS]
    assert len(names) == len(set(names))
    assert len(domains) == len(set(domains))
