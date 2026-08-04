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
    assert sent_request.full_url == "https://www.digistore24.com/api/v1/getUserInfo"


def test_fetch_recent_sales_returns_the_real_data_list_unmodified(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    real_purchases = [{"purchase_id": "12345", "amount": "49.00"}]
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"result": "ok", "data": real_purchases})):
        sales = Digistore24Provider().fetch_recent_sales()

    assert sales == real_purchases  # passed through exactly as the real API sent it, never remapped/renamed


def test_fetch_recent_sales_raises_when_the_response_has_no_real_data_list(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"result": "ok"})):
        with pytest.raises(Digistore24APIError, match="no real 'data' list"):
            Digistore24Provider().fetch_recent_sales()


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


def test_call_raises_clearly_on_malformed_json(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "real-test-key")

    class _BadResponse(_FakeResponse):
        def read(self) -> bytes:
            return b"not json at all"

    with patch("urllib.request.urlopen", return_value=_BadResponse(200, {})):
        with pytest.raises(Digistore24APIError, match="non-JSON body"):
            Digistore24Provider().fetch_recent_sales()
