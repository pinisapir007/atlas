from atlas.brain.cashflow import profit
from atlas.brain.kpi import KPIRegistry
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task, now
from atlas.campaign.registry import CampaignRegistry, refresh_confidence
from atlas.influencer.production import generate_content_package
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.models import ExecutionPlan, ExecutionStep
from atlas.orchestrator.registry import ExecutionPlanRegistry

# Templates a produce_content step cannot proceed without — a campaign
# with no hook or no CTA at all has nothing real to review or publish.
# Every other TEMPLATE_KINDS entry being missing is recorded honestly in
# the step's result but doesn't block it, the same "missing_kinds is an
# honest gap, not a hard failure" discipline generate_content_package()
# already established.
_ESSENTIAL_TEMPLATE_KINDS = {"hook", "cta"}


def start_execution(campaign_id: str, campaign_registry: CampaignRegistry, plan_registry: ExecutionPlanRegistry) -> ExecutionPlan:
    """Builds and persists a fresh ExecutionPlan — "an execution plan with
    ordered tasks and dependencies" (founder's framing): verify_readiness,
    then one produce_content step per campaign.influencer_ids entry (all
    depending on verify_readiness), then one request_founder_review
    depending on every produce_content step, then check_measurement.

    Requires campaign.status == "active" — the founder's explicit
    approval gate (see campaign.registry.set_status()). "Receive an
    approved Campaign from the Decision Engine" is honored today by
    refusing to start execution on anything still "proposed"; the
    Decision Engine doesn't create/approve Campaigns automatically yet
    (see atlas.campaign package docs), so today "approved" means a
    founder explicitly activated it — this function doesn't care how the
    campaign got approved, only that it is.

    Idempotent: returns the existing in_progress plan rather than
    starting a second one for the same campaign.
    """
    campaign = campaign_registry.get_campaign(campaign_id)
    if campaign.status != "active":
        raise ValueError(
            f"campaign {campaign_id} is not active (status={campaign.status!r}) — approve it via campaign.registry.set_status() first"
        )
    existing = [p for p in plan_registry.plans_for_campaign(campaign_id) if p.status == "in_progress"]
    if existing:
        return existing[0]

    verify_step = ExecutionStep(campaign_id=campaign_id, kind="verify_readiness")
    produce_steps = [
        ExecutionStep(campaign_id=campaign_id, kind="produce_content", influencer_id=influencer_id, depends_on=[verify_step.id])
        for influencer_id in campaign.influencer_ids
    ]
    review_step = ExecutionStep(campaign_id=campaign_id, kind="request_founder_review", depends_on=[s.id for s in produce_steps])
    measure_step = ExecutionStep(campaign_id=campaign_id, kind="check_measurement", depends_on=[review_step.id])

    plan = ExecutionPlan(campaign_id=campaign_id, steps=[verify_step, *produce_steps, review_step, measure_step])
    plan.event_log.append({"at": now(), "event": "plan_created", "step_count": len(plan.steps)})
    plan_registry.save_plan(plan)
    return plan


def advance_execution(
    plan_id: str,
    plan_registry: ExecutionPlanRegistry,
    campaign_registry: CampaignRegistry,
    influencer_registry: InfluencerRegistry,
    memory: BrainMemory,
    kpis: KPIRegistry,
    knowledge: KnowledgeBase,
) -> ExecutionPlan:
    """The Orchestrator's core coordination loop — "track execution state
    and failures" and "resume automatically when blocked tasks become
    available" are both satisfied by the same mechanism: every call
    recomputes each step's readiness fresh from current real state (the
    same purity decide()/has_materially_changed() already rely on), so a
    step that was blocked because its precondition wasn't met yet is
    re-evaluated automatically the next time this runs — no separate
    retry mechanism needed. Call repeatedly (see
    advance_all_campaign_executions(), wired into CEOBrain.tick()).

    Never executes business work itself: produce_content only ever calls
    ATLAS's own deterministic Production Layer, and request_founder_review
    only ever creates a real Task — RiskPolicy/Delegator/CEOBrain's
    existing tick() loop is what actually decides and acts on it, on its
    own next cycle. This function coordinates; it never dispatches to a
    Registry asset or writes a KPI/Ledger entry directly.
    """
    plan = plan_registry.get_plan(plan_id)
    if plan.status != "in_progress":
        return plan

    by_id = {s.id: s for s in plan.steps}
    changed = False

    for step in plan.steps:
        if step.status in ("done", "failed"):
            continue

        if step.status == "dispatched":
            task = memory.get_task(step.task_id)
            if task.status == "done":
                step.status = "done"
                step.result = {**step.result, "task_status": "done"}
                step.updated_at = now()
                changed = True
            elif task.status == "failed":
                step.status = "failed"
                step.result = {**step.result, "task_status": "failed"}
                step.updated_at = now()
                changed = True
            continue

        if not all(by_id[dep].status == "done" for dep in step.depends_on):
            continue  # still waiting — leave as pending, re-checked next call

        _perform_step(step, plan, campaign_registry, influencer_registry, memory, kpis, knowledge)
        changed = True

    if changed:
        plan.updated_at = now()
        plan.event_log.append({"at": now(), "event": "steps_advanced", "statuses": {f"{s.kind}:{s.id}": s.status for s in plan.steps}})
        if all(s.status == "done" for s in plan.steps):
            plan.status = "completed"
            campaign = campaign_registry.get_campaign(plan.campaign_id)
            campaign.status = "completed"
            campaign_registry.save_campaign(campaign)
            plan.event_log.append({"at": now(), "event": "plan_completed"})
        plan_registry.save_plan(plan)

    return plan


def _perform_step(
    step: ExecutionStep,
    plan: ExecutionPlan,
    campaign_registry: CampaignRegistry,
    influencer_registry: InfluencerRegistry,
    memory: BrainMemory,
    kpis: KPIRegistry,
    knowledge: KnowledgeBase,
) -> None:
    campaign = campaign_registry.get_campaign(plan.campaign_id)
    step.updated_at = now()

    if step.kind == "verify_readiness":
        _verify_readiness(step, campaign, influencer_registry, memory)
    elif step.kind == "produce_content":
        _produce_content(step, campaign, campaign_registry, influencer_registry)
    elif step.kind == "request_founder_review":
        _dispatch_founder_review(step, campaign, memory)
    elif step.kind == "check_measurement":
        _check_measurement(step, campaign, campaign_registry, knowledge, memory, kpis)


def _verify_readiness(step: ExecutionStep, campaign, influencer_registry: InfluencerRegistry, memory: BrainMemory) -> None:
    known_ids = {i.id for i in influencer_registry.influencers()}
    missing = [i for i in campaign.influencer_ids if i not in known_ids]
    if missing:
        step.status, step.result = "blocked", {"reason": f"unknown influencer id(s): {missing}"}
        return
    if not campaign.influencer_ids:
        step.status, step.result = "blocked", {"reason": "no influencer assigned to this campaign"}
        return
    if campaign.goal_id is None:
        step.status, step.result = "blocked", {"reason": "no Goal linked — call campaign.registry.link_goal() first"}
        return
    known_goal_ids = {g.id for g in memory.goals()}
    if campaign.goal_id not in known_goal_ids:
        # Verified upfront here (not left for check_measurement to discover)
        # so a dangling goal_id surfaces as a clear, honest "blocked" reason
        # rather than an uncaught KeyError several steps later.
        step.status, step.result = "blocked", {"reason": f"linked Goal '{campaign.goal_id}' does not exist"}
        return
    step.status, step.result = "done", {"verified_influencers": campaign.influencer_ids, "goal_id": campaign.goal_id}


def _produce_content(step: ExecutionStep, campaign, campaign_registry: CampaignRegistry, influencer_registry: InfluencerRegistry) -> None:
    package = generate_content_package(campaign.id, step.influencer_id, campaign_registry, influencer_registry)
    missing_essential = sorted(_ESSENTIAL_TEMPLATE_KINDS & set(package.missing_kinds))
    if missing_essential:
        step.status = "blocked"
        step.result = {"reason": f"missing essential templates: {missing_essential}", "missing_kinds": package.missing_kinds}
        return
    step.status = "done"
    step.result = {
        "hooks": len(package.hooks),
        "ctas": len(package.ctas),
        "scripts": len(package.scripts),
        "captions": len(package.captions),
        "missing_kinds": package.missing_kinds,
    }


def _dispatch_founder_review(step: ExecutionStep, campaign, memory: BrainMemory) -> None:
    task = Task(
        goal_id=campaign.goal_id,
        description=f"Founder review requested: launch campaign '{campaign.business_objective}' ({campaign.product_offer})",
        category="campaign_execution",
        reversible=False,
    )
    memory.save_task(task)
    step.task_id = task.id
    step.status = "dispatched"
    step.result = {"task_id": task.id}


def _check_measurement(step: ExecutionStep, campaign, campaign_registry: CampaignRegistry, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> None:
    goal = memory.get_goal(campaign.goal_id)
    measured_profit = profit(goal, kpis)
    if measured_profit is None:
        step.status = "blocked"
        step.result = {"reason": "revenue/cost not yet measured for this campaign's goal"}
        return
    refresh_confidence(campaign.id, knowledge, memory, kpis, campaign_registry)
    step.status = "done"
    step.result = {"profit": measured_profit}


def advance_all_campaign_executions(
    plan_registry: ExecutionPlanRegistry,
    campaign_registry: CampaignRegistry,
    influencer_registry: InfluencerRegistry,
    memory: BrainMemory,
    kpis: KPIRegistry,
    knowledge: KnowledgeBase,
) -> None:
    """CEOBrain.tick()'s bridge into the Execution Orchestrator — the same
    shape every pipeline-advance bridge already has (advance_affiliate_
    pipeline, advance_content_factory, ...): read current real state,
    advance whatever's ready, persist. This is the actual mechanism behind
    "resume automatically when blocked tasks become available.\""""
    for plan in plan_registry.plans():
        if plan.status == "in_progress":
            advance_execution(plan.id, plan_registry, campaign_registry, influencer_registry, memory, kpis, knowledge)
