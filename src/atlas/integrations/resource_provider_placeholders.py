"""Reserved, honest placeholder ResourceProviders (2026-08-04, Resource
Discovery Engine V1) — Google Drive, OneDrive, Dropbox, NAS, and Gmail.

Each satisfies atlas.integrations.base.ResourceProvider structurally
(name/fetch_resources()) so the Resource Discovery Engine can register
and run them exactly like LocalFolderProvider — but none has a real
API/network call anywhere in it. This mirrors the exact "reserved, zero
implementations" precedent already established for
affiliate_provider_placeholders.py, ContentPublisher, and
MarketSignalProvider: picking and building a real, credentialed
integration for any one of these (real OAuth for Drive/OneDrive/
Dropbox/Gmail, a real network path/credential for a NAS) is a separate,
explicit decision for each specific system — not something registering
the class name here implies is ready. fetch_resources() always returns
None (never a fabricated resource, never a fake empty-but-successful
scan) until a real implementation replaces it, the same fail-closed
contract every other unbuilt provider in this codebase already follows.
"""

from atlas.integrations.base import Resource


class GoogleDriveProvider:
    """Placeholder for Google Drive. No real API integration exists —
    a real OAuth app registration and a real, founder-authorized
    connection are a separate, explicit decision not made here."""

    name = "google_drive"

    def fetch_resources(self) -> list[Resource] | None:
        return None


class OneDriveProvider:
    """Placeholder for Microsoft OneDrive. No real API integration
    exists yet — same OAuth/credential decision as Google Drive, not
    made here."""

    name = "onedrive"

    def fetch_resources(self) -> list[Resource] | None:
        return None


class DropboxProvider:
    """Placeholder for Dropbox. No real API integration exists yet."""

    name = "dropbox"

    def fetch_resources(self) -> list[Resource] | None:
        return None


class NASProvider:
    """Placeholder for a network-attached storage device. No real
    network/credential integration exists yet — this is only ever a
    LAN-local decision when a specific real device exists, not made
    here."""

    name = "nas"

    def fetch_resources(self) -> list[Resource] | None:
        return None


class GmailProvider:
    """Placeholder for Gmail (as a resource source, e.g. attachments).
    No real API integration exists yet — same OAuth/credential decision
    as Google Drive, not made here."""

    name = "gmail"

    def fetch_resources(self) -> list[Resource] | None:
        return None
