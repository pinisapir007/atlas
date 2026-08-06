"""ATLAS <-> BrowserObserver Connection V1 (2026-08-06).

The one real function this module exists for: turn a real, allowed
browser observation into a real, durable Finding — the exact same
shape `atlas brain finding add` already produces by hand, just
automated. Deliberately does not touch the Decision Engine, Finding,
or KnowledgeBase in any way: decide()/confidence_score()/
opportunity_ranking already read knowledge.findings() fresh every
call, so a Finding created here is picked up automatically on the
very next tick, with zero additional wiring — the entire point of
reusing the existing model instead of inventing a new one.

Never infers `category`/`subject`/`market` from the page content —
all three are supplied explicitly by the caller (the real research
task that triggered this observation), the same "never guessed,
always '' unless the source states it" discipline Finding.subject/
market already established. This module only ever describes WHERE
the evidence came from (a real URL) and WHAT was actually read
(real, raw page text) — it never decides what the evidence means.
"""

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.integrations.base import BrowserObserver, PageObservation

_DESCRIPTION_MAX_CHARS = 500


class DomainNotApprovedError(ValueError):
    """Raised when the real domain in a requested URL is not on the
    real BrowserAllowlist — fail-closed, the same default-deny
    discipline ResourceAllowlist already enforces for local files,
    applied here to the real, public internet."""


def collect_evidence_from_url(
    url: str,
    category: str,
    source: str,
    observer: BrowserObserver,
    allowlist: BrowserAllowlist,
    knowledge: KnowledgeBase,
    subject: str = "",
    market: str = "",
    extract: dict[str, str] | None = None,
) -> Finding:
    """Navigates to a real, allowed URL, reads its real content, and
    records exactly one real, durable Finding from it. Raises
    DomainNotApprovedError before ever calling `observer` if the
    domain isn't on the real allowlist — the check happens first, not
    as an afterthought. Raises whatever real error `observer.observe()`
    raises on an unrecoverable failure (page unreachable, timeout) —
    never records a Finding from a failed or partial observation.
    """
    if not allowlist.is_approved(url):
        raise DomainNotApprovedError(f"domain not approved for autonomous browsing: {url!r}")

    observation = observer.observe(url, extract=extract)

    finding = Finding(
        source=source,
        category=category,
        description=_real_description(observation),
        evidence=url,
        subject=subject,
        market=market,
    )
    knowledge.save_finding(finding)
    return finding


def _real_description(observation: PageObservation) -> str:
    """The real, raw text actually read from the page — truncated for
    storage size, never summarized or rewritten by this layer. If the
    caller requested specific structured fields (`extract`), those real
    values are included first since they're the most targeted real
    evidence available."""
    if observation.structured_data:
        structured = ", ".join(f"{k}: {v}" for k, v in observation.structured_data.items())
        return f"{structured} — {observation.text_content}"[:_DESCRIPTION_MAX_CHARS]
    return observation.text_content[:_DESCRIPTION_MAX_CHARS]
