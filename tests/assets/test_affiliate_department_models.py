import pytest

from atlas.assets.affiliate_department.models import validate_provider_link


def test_accepts_the_real_custom_domain_aff_link():
    validate_provider_link("digistore24", "https://aifluencersystem.de/start#aff=2026mayabotd1b5")


def test_rejects_a_random_url_with_aff_equals_in_its_path():
    with pytest.raises(ValueError):
        validate_provider_link("digistore24", "https://example.com/aff=123/page")


def test_rejects_an_empty_aff_value():
    with pytest.raises(ValueError):
        validate_provider_link("digistore24", "https://example.com/start#aff=")


def test_accepts_the_generic_digistore24_domain_link():
    validate_provider_link("digistore24", "https://www.digistore24.com/redir/123456/myaffid/")
