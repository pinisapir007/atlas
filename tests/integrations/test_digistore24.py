import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

from atlas.integrations.base import CommerceProvider
from atlas.integrations.digistore24 import Digistore24APIError, Digistore24Provider


class _FakeResponse:
    """A minimal stand-in for the object urllib.request.urlopen()'s
    context manager yields — just enough surface (.status, .read()) for
    _call() to work against, without a real network call."""

    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._body


def test_satisfies_the_commerce_provider_protocol():
    assert isinstance(Digistore24Provider(), CommerceProvider)


def test_declares_the_affiliate_category_it_serves():
    assert Digistore24Provider().category == "affiliate"


def test_accepts_the_generic_digistore24_domain_link():
    assert Digistore24Provider().validate_link("https://www.digistore24.com/redir/123456/myaffid/") is True


def test_accepts_a_real_custom_domain_link_with_aff_parameter():
    provider = Digistore24Provider()
    assert provider.validate_link("https://aifluencersystem.de/start#aff=2026mayabotd1b5") is True


def test_rejects_a_url_with_aff_equals_only_in_its_path():
    provider = Digistore24Provider()
    assert provider.validate_link("https://example.com/aff=123/page") is False


def test_rejects_an_empty_aff_value():
    provider = Digistore24Provider()
    assert provider.validate_link("https://example.com/start#aff=") is False


def test_rejects_non_https():
    provider = Digistore24Provider()
    assert provider.validate_link("http://example.com/start?aff=real123") is False


def test_fetch_recent_sales_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    assert Digistore24Provider().fetch_recent_sales() is None


def test_verify_connection_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    assert Digistore24Provider().verify_connection() is None


def test_call_never_makes_a_network_request_when_no_key_is_configured(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    with patch("urllib.request.urlopen") as urlopen:
        Digistore24Provider().fetch_recent_sales()
        urlopen.assert_not_called()


def test_verify_connection_sends_the_real_auth_header_and_parses_the_response(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"result": "ok", "data": {"email": "founder@example.com"}})) as urlopen:
        result = Digistore24Provider().verify_connection()

    assert result == {"result": "ok", "data": {"email": "founder@example.com"}}
    sent_request = urlopen.call_args[0][0]
    assert sent_request.get_header("X-ds-api-key") == "real-test-key"  # Request.get_header() capitalizes internally
    assert sent_request.full_url == "https://www.digistore24.com/api/call/getUserInfo"


def test_fetch_recent_sales_returns_the_real_purchase_list_unmodified(monkeypatch):
    # Real envelope shape, live-verified 2026-08-06: `data` is a
    # pagination envelope, not the list itself -- the real list is
    # nested under data['purchase_list'].
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    real_purchases = [{"purchase_id": "12345", "amount": "49.00"}]
    real_envelope = {
        "result": "ok",
        "data": {
            "from": "2026-08-05 00:00:00", "to": "2026-08-06 19:29:22",
            "item_count": "1", "page_size": 500, "page_no": 1, "page_count": 1,
            "purchase_list": real_purchases,
        },
    }
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, real_envelope)):
        sales = Digistore24Provider().fetch_recent_sales()

    assert sales == real_purchases  # passed through exactly as the real API sent it, never remapped/renamed


def test_fetch_recent_sales_raises_when_the_response_has_no_real_purchase_list(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"result": "ok"})):
        with pytest.raises(Digistore24APIError, match="no real 'data.purchase_list' list"):
            Digistore24Provider().fetch_recent_sales()


def test_fetch_recent_sales_raises_when_data_is_the_old_wrongly_assumed_bare_list_shape(monkeypatch):
    # Regression guard for the real, live-corrected bug: a bare list
    # under 'data' (the original, wrong assumption) must not silently
    # be accepted as if it were the real envelope shape.
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"result": "ok", "data": [{"purchase_id": "1"}]})):
        with pytest.raises(Digistore24APIError, match="no real 'data.purchase_list' list"):
            Digistore24Provider().fetch_recent_sales()


def test_fetch_recent_sales_returns_a_real_empty_list_when_the_account_has_no_purchases(monkeypatch):
    # The real, live-observed state of this account, 2026-08-06: zero
    # purchases ever, across its full real range -- a genuine, honest
    # empty result, not a failure.
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    real_envelope = {
        "result": "ok",
        "data": {
            "from": "2020-01-01 00:00:00", "to": "2026-08-06 23:59:59",
            "item_count": "0", "page_size": 500, "page_no": 1, "page_count": 0,
            "purchase_list": [],
        },
    }
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, real_envelope)):
        sales = Digistore24Provider().fetch_recent_sales()

    assert sales == []


def test_list_marketplace_entries_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    assert Digistore24Provider().list_marketplace_entries() is None


def test_list_marketplace_entries_sends_the_real_request_and_returns_the_raw_response_unmapped(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    real_response = {"api_version": "1.010", "result": "success", "data": {"entries": [{"id": 123, "stats_stars": 0.83}]}}
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, real_response)) as urlopen:
        result = Digistore24Provider().list_marketplace_entries()

    assert result == real_response  # returned exactly as sent -- not unwrapped, this is a discovery probe
    sent_request = urlopen.call_args[0][0]
    assert sent_request.full_url == "https://www.digistore24.com/api/call/listMarketplaceEntries"


def test_list_marketplace_entries_sends_the_documented_sort_by_parameter(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"result": "success", "data": {"entries": []}})) as urlopen:
        Digistore24Provider().list_marketplace_entries(sort_by="stats_stars")

    sent_request = urlopen.call_args[0][0]
    assert "sort_by=stats_stars" in sent_request.full_url


def test_get_marketplace_entry_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.delenv("DIGISTORE24_API_KEY", raising=False)
    assert Digistore24Provider().get_marketplace_entry("123") is None


def test_get_marketplace_entry_sends_the_entry_id_and_returns_the_raw_response_unmapped(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    real_response = {"api_version": "1.010", "result": "success", "data": {"id": 123, "product_category": "health"}}
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, real_response)) as urlopen:
        result = Digistore24Provider().get_marketplace_entry("123")

    assert result == real_response
    sent_request = urlopen.call_args[0][0]
    assert sent_request.full_url == "https://www.digistore24.com/api/call/getMarketplaceEntry?entry_id=123"


def test_call_raises_clearly_on_http_error_naming_likely_causes(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "wrong-key")
    error = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=BytesIO(b'{"error":"invalid api key"}'))
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(Digistore24APIError, match="HTTP 401"):
            Digistore24Provider().fetch_recent_sales()


def test_call_raises_clearly_on_a_network_error(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route to host")):
        with pytest.raises(Digistore24APIError, match="network error"):
            Digistore24Provider().fetch_recent_sales()


def test_call_raises_on_a_real_api_level_error_envelope_even_with_http_200(monkeypatch):
    # Confirmed by a real, live probe (2026-08-04): Digistore24 signals an
    # API-level failure with HTTP 200 and "result": "error" in the body,
    # not an HTTP error status -- this must be caught explicitly or a real
    # failure would silently read as a successful response.
    monkeypatch.setenv("DIGISTORE24_API_KEY", "wrong-key")
    error_body = {"api_version": "1.2", "result": "error", "message": "No API key given.", "code": 2}
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, error_body)):
        with pytest.raises(Digistore24APIError, match="No API key given"):
            Digistore24Provider().verify_connection()


def test_call_raises_clearly_on_malformed_json(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")

    class _BadResponse(_FakeResponse):
        def read(self) -> bytes:
            return b"not json at all"

    with patch("urllib.request.urlopen", return_value=_BadResponse(200, {})):
        with pytest.raises(Digistore24APIError, match="non-JSON body"):
            Digistore24Provider().fetch_recent_sales()


def test_add_campaign_key_to_real_promocode_affiliate_link():
    from atlas.integrations.digistore24 import add_campaign_key

    result = add_campaign_key(
        "https://KetoDNA.app/d#aff=2026mayabotd1b5",
        "goal-e3ec71a1b9f3",
    )

    assert result == (
        "https://KetoDNA.app/d"
        "#aff=2026mayabotd1b5&cam=goal-e3ec71a1b9f3"
    )


def test_add_campaign_key_to_digistore24_promolink():
    from atlas.integrations.digistore24 import add_campaign_key

    result = add_campaign_key(
        "https://www.digistore24.com/redir/123456/myaffid/",
        "goal-abc123",
    )

    assert result == (
        "https://www.digistore24.com/redir/"
        "123456/myaffid/goal-abc123/"
    )


def test_add_campaign_key_replaces_existing_promocode_campaign_key():
    from atlas.integrations.digistore24 import add_campaign_key

    first = add_campaign_key(
        "https://KetoDNA.app/d#aff=2026mayabotd1b5&cam=old-key",
        "goal-new",
    )
    second = add_campaign_key(first, "goal-new")

    assert first == "https://KetoDNA.app/d#aff=2026mayabotd1b5&cam=goal-new"
    assert second == first


def test_add_campaign_key_leaves_unknown_url_shape_unchanged():
    from atlas.integrations.digistore24 import add_campaign_key

    url = "https://real-network.example/track/abc123"

    assert add_campaign_key(url, "goal-1") == url


def test_add_campaign_key_rejects_invalid_campaign_key():
    import pytest
    from atlas.integrations.digistore24 import add_campaign_key

    with pytest.raises(ValueError, match="campaign_key"):
        add_campaign_key(
            "https://KetoDNA.app/d#aff=affiliate",
            "goal with spaces",
        )


def test_fetch_recent_commissions_reads_documented_items(monkeypatch):
    from atlas.integrations.digistore24 import Digistore24Provider

    monkeypatch.setenv("DIGISTORE24_API_KEY", "test-key")
    provider = Digistore24Provider()

    monkeypatch.setattr(
        provider,
        "_call",
        lambda method, params=None: {
            "api_version": "1.2",
            "result": "success",
            "data": {
                "page_no": 1,
                "page_size": 0,
                "item_count": 1,
                "page_count": 1,
                "items": [
                    {
                        "id": 123,
                        "amount": 12.34,
                        "currency": "EUR",
                        "transaction_id": 987,
                        "purchase_id": "PUR-1",
                    }
                ],
            },
        },
    )

    items = provider.fetch_recent_commissions()

    assert items[0]["id"] == 123
    assert items[0]["amount"] == 12.34
    assert items[0]["purchase_id"] == "PUR-1"


def test_fetch_recent_transactions_reads_documented_shape(monkeypatch):
    from atlas.integrations.digistore24 import Digistore24Provider

    monkeypatch.setenv("DIGISTORE24_API_KEY", "test-key")
    provider = Digistore24Provider()

    monkeypatch.setattr(
        provider,
        "_call",
        lambda method, params=None: {
            "data": {
                "transaction_list": [
                    {"id": 987, "transaction_type": "payment"}
                ]
            }
        },
    )

    items = provider.fetch_recent_transactions()

    assert items == [
        {"id": 987, "transaction_type": "payment"}
    ]


def test_get_purchase_tracking_reads_campaign_key(monkeypatch):
    from atlas.integrations.digistore24 import Digistore24Provider

    monkeypatch.setenv("DIGISTORE24_API_KEY", "test-key")
    provider = Digistore24Provider()

    calls = []

    def fake_call(method, params=None):
        calls.append((method, params))
        return {
            "data": {
                "campaign_key": "goal-abc123",
                "click_id": "click-1",
            }
        }

    monkeypatch.setattr(provider, "_call", fake_call)

    data = provider.get_purchase_tracking("PUR-1")

    assert data["campaign_key"] == "goal-abc123"
    assert calls == [
        ("getPurchaseTracking", {"purchase_id": "PUR-1"})
    ]
