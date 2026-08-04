"""ATLAS Resource Discovery Engine V1 (2026-08-04).

Discovers founder-approved resources across multiple sources through
one shared interface, for the Knowledge Engine (atlas.brain.knowledge)
and Opportunity Discovery Engine (atlas.brain.opportunity_discovery_engine)
to build on next — neither is wired to auto-ingest resources in this
V1; this engine's job is producing a normalized, judgment-free Resource
list, the same "discover, don't decide" boundary confidence.py's
Intelligence layer already draws against the Decision Engine. Turning a
discovered resource into a Finding or an Opportunity is a later,
separate step, deliberately not taken here — this engine collects
metadata only, never interprets file content.

The one invariant every layer of this engine enforces independently:
NEVER scan anything without explicit, durable, founder-recorded
approval. Three layers all have to agree before a single real path is
touched: ResourceAllowlist (atlas.brain.resource_allowlist) is the sole
source of truth for what's approved; LocalFolderProvider
(atlas.integrations.local_folder_provider) refuses to scan anything it
wasn't explicitly constructed with, independent of any caller; and this
module never falls back to a default location if the allow-list is
empty — an empty allow-list means the default LocalFolderProvider is
built with zero folders and structurally returns None.

Local folders are the first real provider; Google Drive, OneDrive,
Dropbox, NAS, and Gmail are registered as honest placeholders
(atlas.integrations.resource_provider_placeholders) — always None,
never fabricated, the same discipline the affiliate provider
placeholders already established one engine over.
"""

from pathlib import Path

from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.store import BrainStore, JSONFileStore
from atlas.integrations.base import Resource, ResourceProvider
from atlas.integrations.local_folder_provider import LocalFolderProvider
from atlas.integrations.resource_provider_placeholders import (
    DropboxProvider,
    GmailProvider,
    GoogleDriveProvider,
    NASProvider,
    OneDriveProvider,
)


class ResourceScanState:
    """Durable record of the last real scan's resource metadata, keyed
    by real path — what makes "new/modified/deleted since last scan"
    answerable without re-deriving it from nothing every call. Reuses
    BrainStore/JSONFileStore, the same pattern every other durable
    record in this codebase already uses."""

    def __init__(self, path: Path = Path(".atlas/resource_scan_state.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"resources": {}}

    def last_scan(self) -> dict[str, dict]:
        return self._read().get("resources", {})

    def save_scan(self, resources: list[Resource]) -> None:
        snapshot = {
            r.path: {
                "resource_type": r.resource_type,
                "size_bytes": r.size_bytes,
                "modified_at": r.modified_at,
                "content_hash": r.content_hash,
            }
            for r in resources
            if not r.error
        }
        self._store.write({"resources": snapshot})


def _default_providers(allowlist: ResourceAllowlist) -> list[ResourceProvider]:
    """Every supported source, registered by default — LocalFolderProvider
    is real, constructed with exactly the real, durably-approved folders
    and never more; the other five are honest placeholders that always
    return None until each gets its own real, credentialed
    implementation. Adding a real implementation for one of them later
    means changing exactly its own class in
    resource_provider_placeholders.py — this list, and everything below
    it in this module, stays unchanged."""
    return [
        LocalFolderProvider(allowlist.approved_folders()),
        GoogleDriveProvider(),
        OneDriveProvider(),
        DropboxProvider(),
        NASProvider(),
        GmailProvider(),
    ]


def _find_duplicates(resources: list[Resource]) -> list[list[str]]:
    """Groups real files sharing the same real content hash — folders,
    symlinks, and errored/unhashable entries are never considered, since
    a missing hash is unmeasured, not a match. Only groups with more
    than one real path are returned."""
    by_hash: dict[str, list[str]] = {}
    for r in resources:
        if r.resource_type == "file" and r.content_hash and not r.error:
            by_hash.setdefault(r.content_hash, []).append(r.path)
    return [paths for paths in by_hash.values() if len(paths) > 1]


def _diff_against_previous(resources: list[Resource], previous: dict[str, dict]) -> tuple[list[str], list[str], list[str]]:
    """Real new/modified/deleted paths since the last saved scan. A
    resource with a real error this scan is excluded from the current-
    state comparison (its metadata couldn't actually be read this time),
    but a previously-known path that no longer appears at all is still
    correctly reported deleted."""
    current = {r.path: r for r in resources if not r.error}
    current_paths = set(current)
    previous_paths = set(previous)

    new_paths = sorted(current_paths - previous_paths)
    deleted_paths = sorted(previous_paths - current_paths)

    modified_paths = []
    for path in sorted(current_paths & previous_paths):
        before = previous[path]
        after = current[path]
        if before.get("content_hash") != after.content_hash or before.get("size_bytes") != after.size_bytes:
            modified_paths.append(path)

    return new_paths, modified_paths, deleted_paths


def scan_resources(
    allowlist: ResourceAllowlist | None = None,
    providers: list[ResourceProvider] | None = None,
    scan_state: ResourceScanState | None = None,
) -> dict:
    """The real discovery pipeline: run every registered provider (real
    LocalFolderProvider plus five honest placeholders by default),
    aggregate every real resource, detect real duplicates (matching
    content hashes) and real changes since the last saved scan, then
    persist this scan as the new baseline for next time.

    Per-provider fault isolation mirrors
    opportunity_discovery_engine.discover_opportunities() exactly: a
    provider that raises, returns None (no approved location, or — for
    a placeholder — not implemented), or returns an empty list is
    recorded in "provider_status" and simply contributes zero resources
    — every other provider still runs.

    NEVER scans anything without explicit, durable approval: with an
    empty ResourceAllowlist, the default LocalFolderProvider is
    constructed with zero approved folders and structurally refuses to
    scan (returns None) — there is no fallback location anywhere in
    this call chain.

    Returns {"resources": [...every real Resource...], "provider_status":
    {...}, "new": [...paths...], "modified": [...paths...], "deleted":
    [...paths...], "duplicates": [[path, path, ...], ...]}.
    """
    if allowlist is None:
        allowlist = ResourceAllowlist()
    if scan_state is None:
        scan_state = ResourceScanState()
    if providers is None:
        providers = _default_providers(allowlist)

    combined: list[Resource] = []
    provider_status: dict[str, dict] = {}

    for provider in providers:
        try:
            resources = provider.fetch_resources()
        except Exception as exc:  # noqa: BLE001 -- deliberate: isolate one provider's failure from every other provider, same discipline as opportunity_discovery_engine
            provider_status[provider.name] = {"count": 0, "error": str(exc)}
            continue

        if resources is None:
            provider_status[provider.name] = {"count": 0, "error": "not available (no approved folders, or not yet implemented)"}
            continue

        real_resources = [r for r in resources if isinstance(r, Resource)]
        provider_status[provider.name] = {"count": len(real_resources), "error": None}
        combined.extend(real_resources)

    previous = scan_state.last_scan()
    new_paths, modified_paths, deleted_paths = _diff_against_previous(combined, previous)
    duplicates = _find_duplicates(combined)
    scan_state.save_scan(combined)

    return {
        "resources": combined,
        "provider_status": provider_status,
        "new": new_paths,
        "modified": modified_paths,
        "deleted": deleted_paths,
        "duplicates": duplicates,
    }
