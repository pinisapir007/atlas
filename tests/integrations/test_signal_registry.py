from atlas.integrations.base import MarketSignalProvider
from atlas.integrations.signal_registry import SIGNAL_PROVIDERS, get_signal_providers


class _FakeSignalProvider:
    name = "fake_trends"
    category = "affiliate"

    def fetch_signals(self):
        return None


def test_signal_providers_registry_starts_empty():
    # No real MarketSignalProvider is integrated yet (2026-08-03) -- adding
    # one is a separate, explicit, credentialed decision. Discovery must
    # honestly find nothing until then, never a fabricated placeholder.
    assert SIGNAL_PROVIDERS == {}


def test_get_signal_providers_returns_nothing_for_any_category_today():
    assert get_signal_providers("affiliate") == []
    assert get_signal_providers("digital_product") == []


def test_fake_provider_satisfies_the_protocol_shape():
    # Verifies the Protocol itself is usable/correct, without registering
    # anything real.
    assert isinstance(_FakeSignalProvider(), MarketSignalProvider)


def test_get_signal_providers_filters_by_category(monkeypatch):
    monkeypatch.setitem(SIGNAL_PROVIDERS, "fake_trends", _FakeSignalProvider())
    try:
        assert get_signal_providers("affiliate") == [SIGNAL_PROVIDERS["fake_trends"]]
        assert get_signal_providers("digital_product") == []
    finally:
        SIGNAL_PROVIDERS.pop("fake_trends", None)
