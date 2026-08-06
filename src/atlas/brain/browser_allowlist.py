"""BrowserAllowlist (2026-08-06, BrowserObserver V1) — the one durable,
explicit record of every domain the founder has actually approved for
autonomous browsing. This is the sole source of truth
browser_research.collect_evidence_from_url() consults before ever
calling a real BrowserObserver — a domain not in this registry is
never visited, no matter what any caller asks for. Mirrors
ResourceAllowlist exactly: default-deny, same JSONFileStore/BrainStore
persistence, same idempotent approve/revoke shape — the identical
safety discipline already proven for local file access, applied one
layer further out to the real, public internet.
"""

from urllib.parse import urlparse

from atlas.brain.store import BrainStore, JSONFileStore
from pathlib import Path


class BrowserAllowlist:
    """Durable record of founder-approved domains — pure CRUD, the same
    shape as ResourceAllowlist/BrandRegistry/InfluencerRegistry. No
    browsing logic lives here; this is purely the approval record."""

    def __init__(self, path: Path = Path(".atlas/browser_allowlist.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"domains": []}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def approve_domain(self, domain: str) -> None:
        """Records real, explicit founder approval for one domain.
        Idempotent — approving an already-approved domain is a no-op,
        never a duplicate entry. `domain` is normalized (lowercased,
        no scheme/path) so "https://Reddit.com/r/x" and "reddit.com"
        are recognized as the same real approval."""
        normalized = _normalize_domain(domain)
        data = self._read()
        if normalized not in data["domains"]:
            data["domains"].append(normalized)
            self._write(data)

    def revoke_domain(self, domain: str) -> None:
        """Removes a domain's approval — the next call onward is
        refused. A no-op if it was never approved."""
        normalized = _normalize_domain(domain)
        data = self._read()
        if normalized in data["domains"]:
            data["domains"].remove(normalized)
            self._write(data)

    def approved_domains(self) -> list[str]:
        return list(self._read()["domains"])

    def is_approved(self, url_or_domain: str) -> bool:
        """True only if the real domain in `url_or_domain` is exactly
        an approved domain, or a real subdomain of one — normalized
        before comparison, so this can't be fooled by scheme, case, or
        a "www." prefix mismatch."""
        normalized = _normalize_domain(url_or_domain)
        for domain in self.approved_domains():
            if normalized == domain or normalized.endswith("." + domain):
                return True
        return False


def _normalize_domain(url_or_domain: str) -> str:
    candidate = url_or_domain.strip().lower()
    if "//" in candidate:
        candidate = urlparse(candidate).netloc
    else:
        candidate = candidate.split("/")[0]
    if candidate.startswith("www."):
        candidate = candidate[len("www."):]
    return candidate
