from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Two genuinely different capability shapes, kept as separate, narrow
# Protocols rather than one "PlatformProvider" interface — the same
# discipline atlas.core.capabilities already uses (Runnable/Triggerable/
# Reportable are separate, not one "Asset" interface). A commerce platform
# (Digistore24, Amazon, AliExpress, Etsy, Shopify, Gumroad) has trackable
# links and sales data; a content platform (YouTube, TikTok, Instagram)
# publishes content — nothing about link-validation or sales data applies
# to the second family, and nothing about publishing applies to the first.
#
# ContentPublisher is defined here (the interface future content-platform
# work will implement) but deliberately has no implementation anywhere yet.
# publishing_gateway is "still, deliberately, a dead end" (CLAUDE.md) — no
# external API call exists anywhere in this codebase — and building a real
# YouTube/TikTok/Instagram publisher (real OAuth, real upload) is a much
# bigger, separately-scoped decision than this layer's job to make.


@runtime_checkable
class CommerceProvider(Protocol):
    """A real-world platform ATLAS can sell through or earn affiliate
    commission from. Every provider (Digistore24 today; Amazon, AliExpress,
    Etsy, Shopify, Gumroad in the future) implements this same shape —
    adding a platform means adding one class satisfying this Protocol and
    one entry in registry.PROVIDERS, never touching atlas.core/atlas.brain
    or any existing provider.
    """

    name: str
    # The Finding/Task category this provider serves (e.g. "affiliate") —
    # what makes it possible to ask "which registered providers are even
    # eligible for this category" without any credential or network call.
    # A structural fact about the provider, not a runtime decision.
    category: str

    def validate_link(self, url: str) -> bool:
        """Whether `url` is a real, correctly-formed tracking/product link
        for this provider. Pure pattern-matching — no network call, so this
        is always safe to call with no credentials configured."""
        ...

    def fetch_recent_sales(self) -> list[dict] | None:
        """Real, live conversion/commission data from this provider's own
        API, if a real credential is configured and the live call is
        actually implemented. None means "not available right now" —
        either no credential is configured, or (honestly, for a provider
        still being built out) the real API call itself doesn't exist yet.
        Never an empty list standing in for "checked, found nothing" when
        nothing was actually checked — that would be exactly the kind of
        fabricated-looking success this codebase's fail-closed rule exists
        to prevent.
        """
        ...


@runtime_checkable
class ContentPublisher(Protocol):
    """A platform ATLAS can publish content to — YouTube, TikTok,
    Instagram, and future content platforms. Reserved: no implementation
    exists yet anywhere in this codebase. Building one is a separate,
    explicitly-scoped decision (real OAuth app registration, real content
    upload, real credentials) — not something this layer's existence
    implies is ready to build."""

    name: str

    def publish(self, content: dict) -> dict: ...


@runtime_checkable
class MarketSignalProvider(Protocol):
    """A real source of external demand/market signal data — search
    trends, a marketplace's product catalog, social platform trending
    topics, and similar (2026-08-03, Opportunity Discovery V1). Reserved,
    the same way ContentPublisher is: no implementation exists yet
    anywhere in this codebase. Picking and integrating one is a separate,
    explicitly-scoped, credentialed decision — not something this
    Protocol's existence implies is ready to build. See
    atlas.integrations.signal_registry, which starts empty for exactly
    this reason.
    """

    name: str
    # The Finding/Task category this signal source is evidence for (e.g.
    # "affiliate") — the same structural, no-credential-required fact
    # CommerceProvider.category already establishes.
    category: str

    def fetch_signals(self) -> list[dict] | None:
        """Real, live demand-signal data from this source, if a real
        credential is configured and the live call is actually
        implemented. None means "not available right now" — no credential
        configured, or the real API call itself isn't built yet. Never an
        empty list standing in for "checked, found nothing" when nothing
        was actually checked — the same fail-closed rule
        CommerceProvider.fetch_recent_sales() already follows."""
        ...


@dataclass
class Opportunity:
    """A normalized, provider-agnostic revenue opportunity (2026-08-04,
    Multi-Source Opportunity Discovery Engine V1) — the one shared shape
    every OpportunityProvider returns, regardless of how different their
    real underlying data is (Digistore24 marketplace stats vs. a future
    provider's own real commission data). Mirrors Finding's "real
    evidence, honestly incomplete" discipline: `score` is None (never a
    fabricated 0.0) until a provider's own real data can compute one,
    and `raw` always carries the real, unmodified source data a
    provider's score was actually computed from, for traceability.
    """

    provider: str
    external_id: str
    title: str
    category: str = ""
    score: float | None = None
    url: str = ""
    raw: dict = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class OpportunityProvider(Protocol):
    """A real source of revenue opportunities for the Opportunity
    Discovery Engine (atlas.brain.opportunity_discovery_engine) —
    narrower and more specific than MarketSignalProvider above (which
    stays reserved for its original, broader scope: search trends,
    social trending topics, and other signals that aren't necessarily a
    scored "opportunity" at all). One real class per real affiliate
    network/marketplace, each normalizing its own real data into the
    same Opportunity shape. Digistore24SignalProvider (atlas.brain.
    digistore24_opportunity_discovery) is the first real implementation;
    the Amazon Associates/AliExpress/CJ/Impact/ShareASale placeholders
    (atlas.integrations.affiliate_provider_placeholders) are honest,
    structural placeholders — reserved, zero real API calls, the same
    "no fabrication" discipline ContentPublisher already established for
    an unbuilt integration."""

    name: str
    category: str

    def fetch_opportunities(self) -> list[Opportunity] | None:
        """Real opportunities from this provider, normalized. None means
        not available right now — no credential configured, or (for a
        placeholder) no real implementation exists yet. Never an empty
        list standing in for "checked, found nothing" when nothing was
        actually checked — the same fail-closed rule every other
        provider Protocol in this codebase already follows."""
        ...


@dataclass
class Resource:
    """A normalized, provider-agnostic discovered resource (2026-08-04,
    Resource Discovery Engine V1) — metadata only, never content.
    `content_hash` exists for change/duplicate detection, not retrieval:
    computing it may require transiently reading a file's real bytes,
    but nothing beyond the digest is ever kept. None for a folder
    (nothing meaningful to hash) or a file whose hash couldn't be
    computed (recorded via `error`, never silently dropped).

    `name` is the real base name (the last path component) — kept
    separate from `path` since a caller querying "what is this called"
    shouldn't have to re-parse a full path. `created_at` is real but
    honestly platform-dependent: on Windows it is a real creation time;
    on POSIX systems the underlying `st_ctime` is the last metadata-
    change time, not creation — never presented as more precise than
    what the real OS actually reports."""

    provider: str
    path: str
    resource_type: str  # "file" | "folder"
    name: str = ""
    size_bytes: int | None = None
    modified_at: str | None = None
    created_at: str | None = None
    content_hash: str | None = None
    raw: dict = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class ResourceProvider(Protocol):
    """A real source of discoverable resources for the Resource
    Discovery Engine (atlas.brain.resource_discovery_engine) — one real
    class per real storage location, each normalizing its own real
    listing into the same Resource shape. LocalFolderProvider
    (atlas.integrations.local_folder_provider) is the first real
    implementation, and the only one permitted to touch anything without
    an explicit, durable, founder-approved allow-list behind it — see
    that module's own docstring for the full safety discipline. The
    Google Drive/OneDrive/Dropbox/NAS/Gmail placeholders
    (atlas.integrations.resource_provider_placeholders) are honest,
    structural placeholders — reserved, zero real API/network calls, the
    same "no fabrication" discipline ContentPublisher/OpportunityProvider
    already established for an unbuilt integration.
    """

    name: str

    def fetch_resources(self) -> list[Resource] | None:
        """Real resources from this provider, normalized. None means not
        available right now — no approved location configured (for
        LocalFolderProvider: an empty allow-list, never a default/implied
        one), or (for a placeholder) no real implementation exists yet.
        Never an empty list standing in for "checked, found nothing" when
        nothing was actually checked — the same fail-closed rule every
        other provider Protocol in this codebase already follows."""
        ...
