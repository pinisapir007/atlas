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
