"""Capital Allocation V1 (2026-08-06, M3 — Business Sense's Allocate
function). Before this module existed, "Business Sense" was really two
narrower functions wearing one name: Evaluate (decision_engine.decide()
— real, but judges one category in isolation) and Govern (RiskPolicy —
real, but answers "is this safe", not "is this the right move"). Never
touching Evaluate/Govern's own logic — this module is a synthesis layer
on top of both, plus the real, already-existing portfolio and Strategist
mechanisms, answering the founder's actual CEO-level questions: open a
new engine, strengthen a proven one, or free resources from a failing
one?

Deliberately reuses every real mechanism this codebase already has
rather than re-deriving a parallel one: decide() for "is there enough
evidence", portfolio_entries()/rank_portfolio() for "what do we already
own and how well is it doing", and SimpleStrategist.reallocate() for
"which currently active goal is this cycle's real pause candidate" —
the exact same check the Strategist itself would apply, not a
second, competing definition of "weak."

AI/compute allocation (the founder's "how do we divide budget, time,
compute, and AI tools" question) stays honestly v1: `ai_providers_note`
is informational only, listing what's registered (via
atlas.integrations.ai_provider_registry, M1) — no real budget or
compute-quota model exists anywhere in this codebase yet, and inventing
one now would be exactly the fabricated-sophistication mistake this
codebase avoids everywhere else. A real quota mechanism is honestly
future work, once real usage data exists to justify how it should be
divided.
"""

from dataclasses import dataclass, field

from atlas.brain.decision_engine import decide
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Decision, Goal, StrategicObjective
from atlas.brain.portfolio import PortfolioEntry, portfolio_entries, rank_portfolio
from atlas.brain.strategist import SimpleStrategist
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry
from atlas.influencer.registry import InfluencerRegistry
from atlas.integrations.ai_provider_registry import AI_PROVIDERS

# Every real verdict decide() can return that means "don't move capital
# yet" -- passed straight through as this module's own action, since
# Evaluate already answered definitively and re-litigating it here would
# be a second, competing judgment of the same question.
_HOLD_VERDICTS = {"insufficient_evidence", "already_invested", "already_proposed", "propose_capability"}


@dataclass
class AllocationRecommendation:
    """One real, explained capital-allocation call for a candidate
    category — the actual mechanism behind "new engine or strengthen an
    existing one, and is anything worth closing right now." Every field
    is either a real object already produced elsewhere in this codebase
    (Decision, PortfolioEntry, Goal) or a plain string reason built from
    them -- nothing here is a new, independently-computed number."""

    category: str
    action: str  # "invest_new" | "strengthen_existing" | one of _HOLD_VERDICTS
    reasoning: str
    decision: Decision
    best_existing_asset: PortfolioEntry | None = None
    pause_candidates: list[dict] = field(default_factory=list)
    ai_providers_note: str = ""
    objective_id: str | None = None


def recommend_allocation(
    category: str,
    knowledge: KnowledgeBase,
    memory: BrainMemory,
    kpis: KPIRegistry,
    influencers: InfluencerRegistry,
    brands: BrandRegistry,
    campaigns: CampaignRegistry,
    objective: StrategicObjective | None = None,
) -> AllocationRecommendation:
    """The real Allocate function: given one candidate category (e.g.
    the output of a `decide()` scan), decides whether the next real
    resource should go toward opening it as a new engine, strengthening
    an already-proven asset that already serves it, or holding because
    Evaluate hasn't cleared it yet -- and separately, always surfaces
    which currently active goal(s) the real Strategist would pause this
    cycle, so a close decision is visible in the same view rather than
    only discoverable after the fact in the log."""
    decision = decide(category, knowledge, memory, kpis)

    entries = rank_portfolio(portfolio_entries(influencers, brands, campaigns, memory, kpis))
    relevant_entries = [e for e in entries if category in e.business_models]
    best_existing_asset = relevant_entries[0] if relevant_entries else None
    proven = best_existing_asset is not None and (best_existing_asset.lifetime_value or 0.0) > 0.0

    if decision.verdict in _HOLD_VERDICTS:
        action = decision.verdict
        reasoning = f"Evaluate has not cleared '{category}' to invest ({decision.verdict}): {decision.reasoning}"
    elif proven:
        action = "strengthen_existing"
        reasoning = (
            f"'{category}' clears the evidence bar to invest, but the portfolio already has a proven asset "
            f"serving it ({best_existing_asset.name}, real lifetime value ${best_existing_asset.lifetime_value:,.2f}) "
            "-- reinforcing a proven asset outranks starting an unproven one."
        )
    else:
        action = "invest_new"
        reasoning = (
            f"'{category}' clears the evidence bar to invest, and no proven existing asset serves it yet "
            "-- real grounds to commit new resources."
        )

    strategist_decisions = SimpleStrategist().reallocate(memory.goals(), kpis, memory.log(), objective=objective)
    pause_candidates = [d for d in strategist_decisions if d["new_status"] == "paused"]
    if pause_candidates:
        goal_descriptions = []
        for d in pause_candidates:
            try:
                goal_descriptions.append(memory.get_goal(d["goal_id"]).description)
            except KeyError:
                continue
        if goal_descriptions:
            reasoning += (
                f" Separately, this cycle's Strategist run would pause {len(pause_candidates)} goal(s) "
                f"({', '.join(goal_descriptions)}) -- real candidates to free resources from."
            )

    return AllocationRecommendation(
        category=category,
        action=action,
        reasoning=reasoning,
        decision=decision,
        best_existing_asset=best_existing_asset,
        pause_candidates=pause_candidates,
        ai_providers_note=(
            f"AI providers available for this work (informational only, no quota enforced yet): "
            f"{', '.join(sorted(AI_PROVIDERS))}"
        ),
        objective_id=objective.id if objective else None,
    )
