import pytest

from atlas.integrations.base import ResourceProvider
from atlas.integrations.resource_provider_placeholders import (
    DropboxProvider,
    GmailProvider,
    GoogleDriveProvider,
    NASProvider,
    OneDriveProvider,
)

ALL_PLACEHOLDERS = [
    (GoogleDriveProvider, "google_drive"),
    (OneDriveProvider, "onedrive"),
    (DropboxProvider, "dropbox"),
    (NASProvider, "nas"),
    (GmailProvider, "gmail"),
]


@pytest.mark.parametrize("provider_class,expected_name", ALL_PLACEHOLDERS)
def test_placeholder_satisfies_the_resource_provider_protocol(provider_class, expected_name):
    assert isinstance(provider_class(), ResourceProvider)


@pytest.mark.parametrize("provider_class,expected_name", ALL_PLACEHOLDERS)
def test_placeholder_declares_its_real_name(provider_class, expected_name):
    assert provider_class().name == expected_name


@pytest.mark.parametrize("provider_class,expected_name", ALL_PLACEHOLDERS)
def test_placeholder_fetch_resources_always_returns_none_never_a_fabricated_scan(provider_class, expected_name):
    # No real API/network integration exists for any of these -- None is
    # the only honest answer, never an empty list (which would read as
    # "we checked and found nothing") and never a fabricated resource.
    assert provider_class().fetch_resources() is None


def test_every_placeholder_has_a_distinct_name():
    names = [provider_class().name for provider_class, _ in ALL_PLACEHOLDERS]
    assert len(names) == len(set(names))
