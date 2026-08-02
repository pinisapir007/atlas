import pytest

from atlas.integrations.digistore24 import Digistore24Provider
from atlas.integrations.registry import PROVIDERS, get_provider


def test_get_provider_returns_the_real_digistore24_instance():
    provider = get_provider("digistore24")
    assert isinstance(provider, Digistore24Provider)


def test_get_provider_raises_on_an_unsupported_platform():
    with pytest.raises(ValueError, match="unsupported provider"):
        get_provider("shopify")


def test_providers_registry_is_the_single_source_of_truth():
    assert set(PROVIDERS) == {"digistore24"}
