from atlas.integrations.base import CommerceProvider
from atlas.integrations.digistore24 import Digistore24Provider


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


def test_fetch_recent_sales_raises_clearly_when_key_present_but_unimplemented(monkeypatch):
    monkeypatch.setenv("DIGISTORE24_API_KEY", "fake-key-for-testing")
    try:
        Digistore24Provider().fetch_recent_sales()
        raised = False
    except NotImplementedError as exc:
        raised = True
        assert "atlas affiliate revenue record" in str(exc)
    assert raised
