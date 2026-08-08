"""recall() (2026-08-09, Memory V1) — the real, unified "what does ATLAS
remember about X" mechanism. Confirmed by direct audit that this did not
exist: every durable store in this codebase (BrainMemory/KnowledgeBase/
DecisionLog/CampaignRegistry/InfluencerRegistry/BrandRegistry/Ledger/
ExecutionPlanRegistry/AffiliateStore/ConversationMemory) was queried only
by whichever specific code already knew to look there — console.py's own
aggregation covers a small, fixed subset (goals/tasks/asset reports/KPIs)
and is not a search mechanism. Real, continuous memory means ATLAS can
answer "what do I know about X" across everything it has ever recorded,
not just recite whichever ten fields console.py happens to show today.

Purely additive, read-only aggregation over already-existing state — the
same "no new data ownership, just a view" discipline console.py's own
build_console_view() already established. Every parameter is optional
and degrades to "not searched" when omitted, mirroring
Reporter.summarize()'s own extension precedent exactly (knowledge/
campaigns/influencers/brands/execution_plans all default to None).

Deliberately a plain, honest substring match (case-insensitive) against
each real record's real text fields — no fabricated relevance score.
Inventing a blended numeric ranking before there's any real signal to
justify one would be exactly the "fabricated-precision" mistake this
codebase's own ranking.py already explicitly avoided for influencer
selection; recency (most-recent-first) is the one honest, real ordering
signal available today.
"""

from dataclasses import dataclass

from atlas.brain.conversation_memory import ConversationMemory
from atlas.brain.decisions import DecisionLog
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory


@dataclass
class MemoryHit:
    store: str
    id: str
    summary: str
    created_at: str


def _matches(query: str, *fields: str) -> bool:
    lowered = query.lower()
    return any(lowered in (f or "").lower() for f in fields)


def recall(
    query: str,
    memory: BrainMemory | None = None,
    knowledge: KnowledgeBase | None = None,
    decisions: DecisionLog | None = None,
    campaigns=None,
    influencers=None,
    brands=None,
    ledger: Ledger | None = None,
    execution_plans=None,
    conversations: ConversationMemory | None = None,
    limit: int = 20,
) -> list[MemoryHit]:
    """Searches every real store passed in for `query` (plain, case-
    insensitive substring match against each record's real text fields),
    returning real hits ordered most-recent-first, capped at `limit`.
    A store left as None is simply not searched — never an error, the
    same graceful-degradation contract Reporter.summarize()'s own
    optional registries already have."""
    hits: list[MemoryHit] = []

    if memory is not None:
        for g in memory.goals():
            if _matches(query, g.description):
                hits.append(MemoryHit("goal", g.id, g.description, g.created_at))
        for t in memory.tasks():
            if _matches(query, t.description, t.category):
                hits.append(MemoryHit("task", t.id, t.description, t.created_at))

    if knowledge is not None:
        for f in knowledge.findings():
            if _matches(query, f.description, f.category, f.subject, f.source):
                hits.append(MemoryHit("finding", f.id, f.description, f.created_at))
        for law in knowledge.success_laws():
            if _matches(query, law.principle, law.source_description):
                hits.append(MemoryHit("success_law", law.id, law.principle, law.created_at))

    if decisions is not None:
        for d in decisions.decisions():
            if _matches(query, d.category, d.reasoning):
                hits.append(MemoryHit("decision", d.id, f"{d.category}: {d.verdict}", d.created_at))

    if campaigns is not None:
        for c in campaigns.campaigns():
            if _matches(query, c.business_objective, c.product_offer, c.category, c.target_audience):
                hits.append(MemoryHit("campaign", c.id, f"{c.product_offer} ({c.category})", c.created_at))

    if influencers is not None:
        for i in influencers.influencers():
            if _matches(query, i.identity.name, " ".join(i.categories)):
                hits.append(MemoryHit("influencer", i.id, i.identity.name, i.created_at))

    if brands is not None:
        for b in brands.brands():
            if _matches(query, b.name, b.niche, b.category):
                hits.append(MemoryHit("brand", b.id, b.name, b.created_at))

    if ledger is not None:
        for e in ledger.entries():
            if _matches(query, e.category, e.provider, e.evidence):
                hits.append(MemoryHit("ledger_entry", e.id, f"{e.kind} {e.amount} ({e.goal_id})", e.created_at))

    if execution_plans is not None:
        for p in execution_plans.plans():
            if _matches(query, p.campaign_id):
                hits.append(MemoryHit("execution_plan", p.id, f"plan for campaign {p.campaign_id}", p.created_at))

    if conversations is not None:
        for entry in conversations.entries():
            if _matches(query, entry.input_line, entry.response_summary):
                hits.append(MemoryHit("conversation", entry.id, entry.input_line, entry.created_at))

    hits.sort(key=lambda h: h.created_at, reverse=True)
    return hits[:limit]
