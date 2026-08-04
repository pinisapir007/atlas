from datetime import datetime, timedelta, timezone

from atlas.brain.asset_value import rank_success_laws_by_track_record, success_law_lifetime_value
from atlas.brain.cashflow import goal_cash_flow
from atlas.brain.confidence import confidence_score, rank_by_confidence
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunity_ranking import rank_opportunities
from atlas.brain.portfolio import portfolio_entries, rank_portfolio
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry

PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}

# How many ranked entries the executive report shows per section — a
# report is a summary, not a full dump; the underlying `atlas brain
# opportunities --explain` / `atlas brain law list` / `atlas portfolio`
# CLI commands remain the place to see everything.
_REPORT_TOP_N = 5


class Reporter:
    """Synthesizes memory + KPIs into a structured executive summary:
    results, opportunities, risks, and recommendations. Plain-dict shaped
    so a future delivery channel (email/Slack) can consume it without
    rework — that channel isn't built here.

    The `knowledge`/`campaigns`/`influencers`/`brands`/`execution_plans`
    registries are optional (2026-08-03, "Daily Executive Report" —
    founder's operational workflow step 12): every existing caller that
    only ever passed memory/kpis keeps working unchanged, degrading to
    empty sections rather than a new required-argument break. CEOBrain
    passes the real registries it already holds, so the report a founder
    actually sees is real end to end. Every new section below is a read-
    only view over already-existing, already-tested ranking functions
    (confidence_score/rank_opportunities/rank_success_laws_by_track_record/
    rank_portfolio) — no new scoring or business logic is introduced here.
    """

    def summarize(
        self,
        period: str,
        memory: BrainMemory,
        kpis: KPIRegistry,
        knowledge: KnowledgeBase | None = None,
        campaigns: CampaignRegistry | None = None,
        influencers: InfluencerRegistry | None = None,
        brands: BrandRegistry | None = None,
        execution_plans: ExecutionPlanRegistry | None = None,
    ) -> dict:
        if period not in PERIOD_DAYS:
            raise ValueError(f"unknown period: {period} (expected one of {sorted(PERIOD_DAYS)})")
        since = (datetime.now(timezone.utc) - timedelta(days=PERIOD_DAYS[period])).isoformat()

        tasks = memory.tasks()
        goals = memory.goals()
        proposals = memory.proposals()

        by_status: dict[str, int] = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1

        return {
            "period": period,
            "active_goals": [g.description for g in goals if g.status == "active"],
            "tasks_by_status": by_status,
            "pending_approvals": [
                {"id": t.id, "description": t.description, "category": t.category}
                for t in tasks
                if t.status == "pending_approval"
            ],
            "blocked_opportunities": [
                {
                    "id": t.id,
                    "description": t.description,
                    "reason": t.history[-1]["reason"] if t.history else "",
                }
                for t in tasks
                if t.status == "blocked"
            ],
            "open_proposals": [
                {"id": p.id, "kind": p.kind, "rationale": p.rationale, "status": p.status}
                for p in proposals
                if p.status != "rejected"
            ],
            "kpi_deltas": {name: kpis.delta(name, since) for name in kpis.names()},
            "cash_flow": goal_cash_flow(goals, kpis),
            "reallocations": [
                {
                    "goal_id": entry["goal_id"],
                    "description": _goal_description(entry["goal_id"], memory),
                    "horizon": entry.get("horizon"),
                    "old_priority": entry.get("old_priority"),
                    "new_priority": entry.get("new_priority"),
                    "old_status": entry.get("old_status"),
                    "new_status": entry.get("new_status"),
                    "reason": entry.get("reason"),
                }
                for entry in memory.log()
                if entry.get("kind") == "reallocation" and entry.get("at", "") >= since
            ],
            "opportunities": _opportunity_summary(knowledge, memory, kpis, since),
            "success_laws": _success_law_summary(knowledge, campaigns, memory, kpis),
            "asset_portfolio": _asset_portfolio_summary(influencers, brands, campaigns, memory, kpis),
            "publishing_readiness": _publishing_readiness_summary(execution_plans),
        }


def _goal_description(goal_id: str, memory: BrainMemory) -> str:
    try:
        return memory.get_goal(goal_id).description
    except KeyError:
        return ""


def _opportunity_summary(knowledge: KnowledgeBase | None, memory: BrainMemory, kpis: KPIRegistry, since: str) -> dict:
    """"Scan for opportunities. Rank them." (workflow steps 1-2) reflected
    in the report: how much new evidence arrived this period, and the
    current real, evidence-ranked category/subject standings — reusing
    confidence_score()/rank_opportunities() exactly as `atlas brain
    opportunities --explain` already does, never a separate computation."""
    if knowledge is None:
        return {"findings_this_period": 0, "categories_ranked": []}

    findings = knowledge.findings()
    categories = sorted({f.category for f in findings})
    ranked = rank_by_confidence([confidence_score(c, knowledge, memory, kpis) for c in categories])

    categories_ranked = []
    for result in ranked:
        subjects = rank_opportunities(result["category"], knowledge)
        top_subject = subjects[0] if subjects else None
        categories_ranked.append(
            {
                "category": result["category"],
                "confidence": result["score"],
                "top_subject": top_subject["subject"] if top_subject else None,
                "top_subject_score": top_subject["score"] if top_subject else None,
                "recommended_market": (top_subject["recommended_market"] or None) if top_subject else None,
            }
        )

    return {
        "findings_this_period": len([f for f in findings if f.created_at >= since]),
        "categories_ranked": categories_ranked,
    }


def _success_law_summary(knowledge: KnowledgeBase | None, campaigns: CampaignRegistry | None, memory: BrainMemory, kpis: KPIRegistry) -> dict:
    """"Update Success Laws" (workflow step 11): there is no mutable
    "current value" to update — real track record is recomputed live from
    real campaign outcomes every time it's read (see
    asset_value.success_law_lifetime_value()), so surfacing it here IS the
    update, the same "nothing is permanently true, recompute fresh"
    discipline the Decision Engine already relies on. Authoring a *new*
    law's principle text remains a founder/analyst judgment call
    (`atlas brain law add`) — no standing policy authorizes generating
    business-principle prose the way identity/brand creative fields are
    (explicit "AI-suggested draft" policy), so none is fabricated here."""
    if knowledge is None or campaigns is None:
        return {"total": 0, "evidence_backed": 0, "ranked_by_track_record": []}

    laws = knowledge.success_laws()
    ranked = rank_success_laws_by_track_record(laws, campaigns, memory, kpis)
    return {
        "total": len(laws),
        "evidence_backed": len([law for law in laws if law.evidence_finding_ids]),
        "ranked_by_track_record": [
            {
                "id": law.id,
                "principle": law.principle,
                "evidence_backed": bool(law.evidence_finding_ids),
                "real_track_record": success_law_lifetime_value(law.id, campaigns, memory, kpis),
            }
            for law in ranked[:_REPORT_TOP_N]
        ],
    }


def _asset_portfolio_summary(
    influencers: InfluencerRegistry | None,
    brands: BrandRegistry | None,
    campaigns: CampaignRegistry | None,
    memory: BrainMemory,
    kpis: KPIRegistry,
) -> list[dict]:
    """"Match or reuse existing company assets" (workflow step 4) is only
    trustworthy if the founder can see which real assets are actually
    earning — the same portfolio.rank_portfolio() view `atlas portfolio`
    already exposes, top N by real lifetime value."""
    if influencers is None or brands is None or campaigns is None:
        return []

    ranked = rank_portfolio(portfolio_entries(influencers, brands, campaigns, memory, kpis))
    return [
        {
            "asset_type": entry.asset_type,
            "asset_id": entry.asset_id,
            "name": entry.name,
            "market": entry.market,
            "lifetime_value": entry.lifetime_value,
        }
        for entry in ranked[:_REPORT_TOP_N]
    ]


def _publishing_readiness_summary(execution_plans: ExecutionPlanRegistry | None) -> dict:
    """"Prepare complete campaign packages" (workflow step 6): how many
    real publishing packages (landing page + creative brief, see
    orchestrator._produce_content()) ATLAS has actually prepared and how
    many campaigns are still blocked on a real, named requirement —
    counted directly from ExecutionStep.result, never re-derived."""
    if execution_plans is None:
        return {"packages_ready": 0, "steps_blocked": []}

    produce_steps = [s for plan in execution_plans.plans() for s in plan.steps if s.kind == "produce_content"]
    return {
        "packages_ready": len([s for s in produce_steps if s.status == "done" and s.result.get("landing_page_path")]),
        "steps_blocked": [
            {"campaign_id": s.campaign_id, "influencer_id": s.influencer_id, "reason": s.result.get("reason", "")}
            for s in produce_steps
            if s.status == "blocked"
        ],
    }
