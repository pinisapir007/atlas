"""Business Plan Generator (Milestone 4, docs/DESIGN_BUSINESS_PLAN_GENERATOR.md,
docs/ARCHITECTURE_INTENT_BUSINESS_PLAN_GENERATOR.md, docs/
CAPABILITY_DEFINITION_BUSINESS_PLAN_GENERATOR.md -- all locked before this
was written) -- the real, missing bridge between a Milestone-3-committed
Universal Core Opportunity (atlas.brain.models.Opportunity, goal_id already
set by revenue_strategy.commit_ready_opportunities()) and a real Campaign,
reusing campaign_advance.py's existing, unmodified
"selected_for_marketing" -> Campaign mechanism.

Scoped to "affiliate" only (BRIDGED_CATEGORIES) -- the one category with a
real execution channel today, locked, not extended here. Never touches the
Universal Core, campaign_advance.py, Campaign, create_campaign(), or
_request_founder_choice().

Two responsibilities, matching the Design's own split -- Capability
Definition's own honest finding: this is primarily Integration/Wiring, not
new business judgment. Every real decision (whether/how much/which model to
commit to) already happened in Milestone 3.

1. advance_business_plan_generation() -- runs every tick, after
   revenue_strategy.commit_ready_opportunities(). For every committed
   Opportunity with no real AffiliateOpportunity yet, creates exactly one
   founder-facing Task asking for the one thing ATLAS structurally cannot
   know itself: real commercial terms. Never creates an AffiliateOpportunity
   itself -- that is the second responsibility, gated behind founder
   approval.

2. create_affiliate_opportunity_from_terms() -- the founder-invoked
   counterpart, same family as influencer.factory.
   create_influencer_from_proposal()/brand.factory.create_brand_from_proposal():
   fail-closed on the linked Task actually being approved (task.status ==
   "done", reached only via the existing structural Proposal/approve path --
   COMMERCIAL_TERMS_TASK_CATEGORY is in models.ALWAYS_REQUIRES_APPROVAL
   purely for this) before it will do anything -- the real enforcement of
   "Milestone 3 decides WHAT, Milestone 4 only continues HOW, never a
   re-choice." Creates the real AffiliateOpportunity directly at
   "selected_for_marketing" -- never at "ranked"/"discovered" -- so it
   structurally can never be seen by affiliate_intelligence_advance.
   _request_founder_choice() or _continue_in_progress_goals(), not because
   of an added bypass but because those functions only ever look at
   different stages. Re-derives every field fresh from the real Universal
   Core Opportunity via task.source_opportunity_id, never trusting a stale
   copy -- the same discipline create_influencer_from_proposal() already
   established.
"""

from atlas.assets.affiliate_department.models import AffiliateOpportunity, validate_provider_link
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.opportunities import OpportunityStore

# The one category with a real execution channel today -- mirrors
# campaign_advance.BRIDGED_CATEGORIES exactly, kept as its own small
# constant here rather than importing that module's private set, since
# extending either independently should never require touching the other
# (the same reasoning opportunity_discovery_advance.py already established
# for its own copy of this same constant).
BRIDGED_CATEGORIES = {"affiliate"}

COMMERCIAL_TERMS_TASK_CATEGORY = "affiliate_commercial_terms_needed"


def advance_business_plan_generation(
    memory: BrainMemory, opportunities: OpportunityStore, affiliate_store: AffiliateStore
) -> list[Task]:
    """For every real, Milestone-3-committed Opportunity (goal_id is not
    None) in a bridged category, with no real AffiliateOpportunity yet for
    that goal: creates exactly one founder-facing Task requesting real
    commercial terms. Never a choice -- the Subject is already decided;
    this only ever asks for the one input ATLAS cannot obtain itself.

    Idempotent: a goal that already has any real AffiliateOpportunity
    (pending terms or already selected_for_marketing) is skipped entirely,
    mirroring campaign_advance.py's own claimed_goal_ids dedup. A goal
    already asked once is never asked again, mirrored via
    Task.source_opportunity_id, the same correlation key every other
    capability-gap task in this codebase already uses for this exact
    purpose."""
    claimed_goal_ids = {o.goal_id for o in affiliate_store.opportunities() if o.goal_id is not None}
    already_asked_ids = {
        t.source_opportunity_id
        for t in memory.tasks()
        if t.category == COMMERCIAL_TERMS_TASK_CATEGORY and t.source_opportunity_id is not None
    }

    new_tasks: list[Task] = []
    for category in BRIDGED_CATEGORIES:
        for opportunity in opportunities.by_category(category):
            if opportunity.goal_id is None:
                continue  # not yet committed by Milestone 3
            if opportunity.goal_id in claimed_goal_ids:
                continue  # already has a real AffiliateOpportunity
            if opportunity.id in already_asked_ids:
                continue  # already asked once -- never repeated

            new_tasks.append(_commercial_terms_task(opportunity))

    return new_tasks


def _commercial_terms_task(opportunity) -> Task:
    return Task(
        goal_id=opportunity.goal_id,
        description=(
            f"Committed via Revenue Strategy (Milestone 3): '{opportunity.subject}' "
            f"({opportunity.category}, market={opportunity.recommended_market or 'unspecified'}). "
            "ATLAS has already decided to pursue this -- the only missing input is real commercial "
            "terms (provider, commission, tracking link), which ATLAS cannot obtain itself. Approve "
            "this task, then run 'atlas affiliate commercial-terms supply <task_id> --provider ... "
            "--commission ... --link ...' with the real terms to continue."
        ),
        category=COMMERCIAL_TERMS_TASK_CATEGORY,
        reversible=False,
        source_opportunity_id=opportunity.id,
    )


def create_affiliate_opportunity_from_terms(
    task_id: str,
    memory: BrainMemory,
    opportunities: OpportunityStore,
    affiliate_store: AffiliateStore,
    commission_per_conversion: float,
    real_affiliate_link: str,
    provider: str,
    provider_product_id: str = "",
) -> AffiliateOpportunity:
    """Materializes a real AffiliateOpportunity, directly at
    "selected_for_marketing", from an approved commercial-terms request
    (see advance_business_plan_generation()). Fail-closed on both ways this
    could go wrong, mirroring influencer.factory.
    create_influencer_from_proposal() exactly: raises if `task_id` isn't
    actually a real commercial-terms request, and raises if it hasn't
    actually been approved yet -- task.status only reaches "done" via the
    structural Proposal/approve path (models.ALWAYS_REQUIRES_APPROVAL),
    never before."""
    task = memory.get_task(task_id)
    if task.category != COMMERCIAL_TERMS_TASK_CATEGORY or task.source_opportunity_id is None:
        raise ValueError(f"{task_id} is not a real affiliate commercial-terms request")
    if task.status != "done":
        raise ValueError(f"{task_id} has not been approved yet")
    if commission_per_conversion <= 0.0:
        raise ValueError(
            "commission_per_conversion must be a real, positive value -- 0.0 means 'not yet known', never a real deal"
        )
    validate_provider_link(provider, real_affiliate_link)  # raises ValueError on an invalid link

    if any(o.goal_id == task.goal_id for o in affiliate_store.opportunities()):
        raise ValueError(f"an AffiliateOpportunity already exists for goal {task.goal_id}")

    source = opportunities.get_opportunity(task.source_opportunity_id)

    result = AffiliateOpportunity(
        product_name=source.subject,
        description=source.description,
        category=source.category,
        commission_per_conversion=commission_per_conversion,
        competition=source.competition if source.competition is not None else 0.0,
        real_affiliate_link=real_affiliate_link,
        provider=provider,
        provider_product_id=provider_product_id,
        marketing_niche=source.marketing_niche,
        recommended_market=source.recommended_market,
        score=source.score if source.score is not None else 0.0,
        notes=(
            f"Committed via Revenue Strategy (Milestone 3) for Goal {task.goal_id}. "
            f"Evidence: {len(source.evidence_finding_ids)} finding(s)."
        ),
        goal_id=task.goal_id,
    )
    result.transition(
        "selected_for_marketing",
        "founder supplied real commercial terms for a Milestone-3-committed opportunity",
    )
    affiliate_store.save_opportunity(result)
    return result
