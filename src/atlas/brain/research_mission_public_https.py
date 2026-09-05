"""Research Mission-specific public HTTPS read policy.

This policy exists ONLY for Research Mission web evidence collection.

It does not change BrowserAllowlist, does not approve any domain, and
does not grant browser action/login/write capability anywhere else in
ATLAS.

Allowed:
- public HTTPS pages;
- default HTTPS port / explicit 443;
- publicly-routable DNS/IP destinations.

Rejected:
- HTTP or other schemes;
- credentials embedded in URLs;
- non-443 ports;
- localhost / local-only hostnames;
- private, loopback, link-local, multicast, reserved, unspecified, or
  otherwise non-global IP destinations;
- DNS names that resolve to any non-global address;
- unresolved/ambiguous targets.

BrowserUseObserver still re-checks this policy against the real URL after
navigation and again after its readiness wait before page text is read.

This is an application-layer target policy, not a substitute for a
network egress firewall. It prevents ATLAS from intentionally accepting
private/non-public destinations and prevents redirected private content
from being trusted/read, while infrastructure-level DNS-rebinding
hardening remains a separate network-control concern.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlparse


_BLOCKED_HOSTS = {
    "localhost",
    "metadata",
    "metadata.google.internal",
    "instance-data",
}

_BLOCKED_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".home.arpa",
    ".lan",
)


class ResearchMissionPublicHTTPSPolicy:
    """Duck-compatible `is_approved()` policy for BrowserPlugin.

    BrowserPlugin expects an allowlist-like object exposing is_approved().
    Supplying this policy to a Research Mission-only BrowserPlugin lets us
    reuse BrowserPlugin/BrowserUseObserver without modifying the global
    BrowserAllowlist or knowledge-source registry.
    """

    def __init__(
        self,
        resolver: Callable[..., list] | None = None,
    ):
        self._resolver = resolver if resolver is not None else socket.getaddrinfo

    @staticmethod
    def _public_ip(address: str) -> bool:
        candidate = address.split("%", 1)[0].strip()

        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError:
            return False

        # IPv4-mapped IPv6 must inherit the mapped IPv4 address's scope.
        mapped = getattr(parsed, "ipv4_mapped", None)
        if mapped is not None:
            parsed = mapped

        return bool(parsed.is_global)

    def is_approved(self, url: str) -> bool:
        """Return True only for a resolvably public HTTPS destination."""

        try:
            parsed = urlparse(url)
        except (TypeError, ValueError):
            return False

        if parsed.scheme.lower() != "https":
            return False

        if parsed.username is not None or parsed.password is not None:
            return False

        hostname = (parsed.hostname or "").rstrip(".").lower()
        if not hostname:
            return False

        try:
            port = parsed.port
        except ValueError:
            return False

        if port not in (None, 443):
            return False

        if "%" in hostname:
            return False

        if hostname in _BLOCKED_HOSTS:
            return False

        if any(hostname.endswith(suffix) for suffix in _BLOCKED_SUFFIXES):
            return False

        # Literal IP: validate directly, never perform DNS.
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            return self._public_ip(hostname)

        # Single-label DNS names are treated as local/internal rather than
        # guessed to be globally routable.
        if "." not in hostname:
            return False

        try:
            answers = self._resolver(
                hostname,
                443,
                type=socket.SOCK_STREAM,
            )
        except (OSError, socket.gaierror, ValueError):
            return False

        addresses: set[str] = set()

        for answer in answers:
            try:
                sockaddr = answer[4]
                address = str(sockaddr[0]).strip()
            except (IndexError, TypeError):
                return False

            if not address:
                return False

            addresses.add(address)

        if not addresses:
            return False

        # Fail closed if even ONE returned address is not globally routable.
        # This prevents a mixed public/private DNS answer from being treated
        # as public merely because one safe address was also present.
        return all(
            self._public_ip(address)
            for address in addresses
        )
