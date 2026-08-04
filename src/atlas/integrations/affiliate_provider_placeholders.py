"""Reserved, honest placeholder OpportunityProviders (2026-08-04,
Multi-Source Opportunity Discovery Engine V1) — Amazon Associates,
AliExpress Affiliate, CJ (Commission Junction), Impact, and ShareASale.

Each satisfies atlas.integrations.base.OpportunityProvider structurally
(name/category/fetch_opportunities()) so the Opportunity Discovery
Engine can register and run them exactly like Digistore24 — but none
has a real API call anywhere in it. This mirrors the exact "reserved,
zero implementations" precedent ContentPublisher and MarketSignalProvider
already established for platforms this codebase hasn't connected yet
(atlas.integrations.base): picking and building a real, credentialed
integration for any one of these is a separate, explicit decision for
each specific network — not something registering the class name here
implies is ready. fetch_opportunities() always returns None (never a
fabricated opportunity, never a fake empty-but-successful check) until
a real implementation replaces it, the same fail-closed contract every
other unbuilt provider in this codebase already follows.
"""

from atlas.integrations.base import Opportunity


class AmazonAssociatesProvider:
    """Placeholder for the Amazon Associates affiliate program. No real
    API integration exists — Amazon's Product Advertising API requires
    its own separate credentialed decision (a real Associates account
    in good standing, real AWS-style signed requests) not made here."""

    name = "amazon_associates"
    category = "affiliate"

    def fetch_opportunities(self) -> list[Opportunity] | None:
        return None


class AliExpressAffiliateProvider:
    """Placeholder for the AliExpress Affiliate program. No real API
    integration exists — a separate, explicit, credentialed decision,
    same as every other unbuilt provider here."""

    name = "aliexpress_affiliate"
    category = "affiliate"

    def fetch_opportunities(self) -> list[Opportunity] | None:
        return None


class CJProvider:
    """Placeholder for CJ Affiliate (formerly Commission Junction). No
    real API integration exists yet."""

    name = "cj"
    category = "affiliate"

    def fetch_opportunities(self) -> list[Opportunity] | None:
        return None


class ImpactProvider:
    """Placeholder for Impact (impact.com). No real API integration
    exists yet."""

    name = "impact"
    category = "affiliate"

    def fetch_opportunities(self) -> list[Opportunity] | None:
        return None


class ShareASaleProvider:
    """Placeholder for ShareASale. No real API integration exists yet."""

    name = "shareasale"
    category = "affiliate"

    def fetch_opportunities(self) -> list[Opportunity] | None:
        return None
