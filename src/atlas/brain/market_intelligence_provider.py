"""FindingsMarketIntelligenceProvider (2026-08-05, ATLAS Intelligence
Engine V1) — the first real IntelligenceProvider.

Deliberately not a new external data source: it normalizes this
codebase's own already-real, already-recorded Finding evidence
(atlas.brain.knowledge.KnowledgeBase) into the new Intelligence shape.
Every real Finding this codebase has ever recorded — from founder-
curated research to Opportunity Discovery's own real, evidence-backed
subjects — is honest, real evidence about a market/channel, so treating
it as market intelligence is a real, defensible mapping, not a stretch.
A more granular sub-domain breakdown (demand vs. supply vs. pricing vs.
trends) doesn't exist in the real data yet — this provider doesn't
invent one; every Intelligence object it returns stays a general
"market" observation until real data exists to split it further.

Read-only: KnowledgeBase.findings() is the only real thing this
provider ever touches, and it's never written to. Timestamps come from
the injected TimeService (Time Awareness Engine V1) — no bare
datetime.now() anywhere in this module, the same "no subsystem reads
system time directly" discipline that engine already established.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.time_service import TimeService
from atlas.integrations.base import Intelligence


class FindingsMarketIntelligenceProvider:
    """Wraps KnowledgeBase.findings() as real market Intelligence.
    Domain logic (normalization only, no scoring/interpretation) lives
    here rather than in atlas.integrations, since it depends on
    KnowledgeBase — the same layering atlas.brain.digistore24_
    opportunity_discovery already established (brain building on
    integrations-adjacent primitives, never the reverse)."""

    name = "findings_market_intelligence"
    domain = "market"

    def __init__(self, knowledge: KnowledgeBase | None = None, time_service: TimeService | None = None):
        self._knowledge = knowledge if knowledge is not None else KnowledgeBase()
        self._time_service = time_service if time_service is not None else TimeService()

    def fetch_intelligence(self) -> list[Intelligence] | None:
        """Every real Finding, normalized. Real empty list (never None)
        when KnowledgeBase genuinely has zero Findings yet — this is
        always "available" (a local file, no credential needed), so an
        empty real check is a real result, not an unavailability."""
        collected_at = self._time_service.iso_timestamp()
        return [
            Intelligence(
                provider=self.name,
                domain=self.domain,
                subject=finding.subject or finding.category,
                summary=finding.description,
                source=finding.source,
                evidence=finding.evidence,
                market=finding.market,
                collected_at=collected_at,
                raw={"finding_id": finding.id, "category": finding.category, "provider": finding.provider, "created_at": finding.created_at},
            )
            for finding in self._knowledge.findings()
        ]
