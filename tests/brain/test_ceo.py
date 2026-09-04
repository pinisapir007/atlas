from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.ceo import CEOBrain
from atlas.brain.decisions import DecisionLog
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task
from atlas.brain.opportunities import OpportunityStore
from atlas.campaign.registry import CampaignRegistry, create_campaign, set_status
from atlas.core.registry import Registry
from atlas.core.store import JSONStore
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.orchestrator import start_execution
from atlas.orchestrator.registry import ExecutionPlanRegistry


def _brain(tmp_path):
    return CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
        knowledge=KnowledgeBase(tmp_path / "knowledge.json"),
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
        campaigns=CampaignRegistry(tmp_path / ".atlas" / "campaigns.json"),
        influencers=InfluencerRegistry(tmp_path / ".atlas" / "influencers.json"),
        execution_plans=ExecutionPlanRegistry(tmp_path / ".atlas" / "execution_plans.json"),
        affiliate_store=AffiliateStore(tmp_path / ".atlas" / "affiliate_intelligence.json"),
        opportunities=OpportunityStore(tmp_path / ".atlas" / "opportunities.json"),
        marketplace_catalog=MarketplaceCatalogStore(tmp_path / ".atlas" / "marketplace_catalog.json"),
        investigations=InvestigationStore(tmp_path / ".atlas" / "investigations.json"),
    )


def test_default_registry_wires_research_discovery_to_this_brains_own_knowledge(tmp_path):
    # Qualification Run #1 root cause, gap #7 (docs/QUALIFICATION_RUN_2026-08-11.md):
    # Registry._instance() has no way to pass real constructor arguments to a
    # lazily-imported asset, so research_discovery previously always fell back
    # to its own default KnowledgeBase() -- never the one this CEOBrain
    # actually reads Findings from. Deliberately NOT passing `registry=` here
    # -- this exercises CEOBrain's own default-Registry-construction path,
    # the one real path this fix touches (an explicitly-provided Registry,
    # like every other test in this file uses, is never auto-seeded).
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    brain = CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        knowledge=kb,
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
        campaigns=CampaignRegistry(tmp_path / ".atlas" / "campaigns.json"),
        influencers=InfluencerRegistry(tmp_path / ".atlas" / "influencers.json"),
        execution_plans=ExecutionPlanRegistry(tmp_path / ".atlas" / "execution_plans.json"),
        affiliate_store=AffiliateStore(tmp_path / ".atlas" / "affiliate_intelligence.json"),
    )

    research_discovery_instance = brain.registry._instance("research_discovery")

    assert research_discovery_instance._knowledge is kb
    assert research_discovery_instance._knowledge is brain.knowledge


def test_tick_blocks_a_new_goal_when_no_registered_asset_matches_its_category(tmp_path):
    """Replaces test_tick_delegates_a_new_goal_to_a_capable_fallback_asset
    (2026-08-15, Delegator Fail-Closed Fix, Foundation Design approved).
    Category "analyze_revenue" matches no asset with a real, working
    entrypoint (`analytics` declares the category but is registered
    metadata-only, no entrypoint at all) — this used to fall through to
    Delegator's unmatched-fallback path (whichever unrelated Triggerable
    asset happened to be first in id order, e.g. MAYA). The new, approved
    intent is "fail closed; never guess a capability" — this task must now
    honestly report blocked, not silently land on an unrelated asset."""
    brain = _brain(tmp_path)
    brain.add_goal("Grow monthly revenue", priority=1)

    tasks = brain.tick()

    assert len(tasks) == 1
    assert tasks[0].assigned_asset_id is None
    assert tasks[0].status == "blocked"


def test_risky_task_requires_approval_not_delegation(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("Reallocate the marketing budget", priority=1)
    task = Task(
        goal_id=goal.id,
        description="Spend on ads",
        category="reallocate_budget",
        estimated_amount=5000,
    )
    brain.memory.save_task(task)

    brain.tick()

    reloaded = brain.memory.get_task(task.id)
    assert reloaded.status == "pending_approval"
    assert reloaded.assigned_asset_id is None


def test_approve_delegates_previously_gated_task(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g", priority=1)
    task = Task(
        goal_id=goal.id,
        description="Spend on ads",
        category="reallocate_budget",
        estimated_amount=5000,
    )
    brain.memory.save_task(task)
    brain.tick()

    approved = brain.approve(task.id)

    # 2026-08-15, Delegator Fail-Closed Fix: "reallocate_budget" matches no
    # asset with a real entrypoint (`cfo` declares the category but is
    # registered metadata-only) -- this used to land on an unrelated
    # fallback asset; now it honestly reports blocked instead.
    assert approved.status == "blocked"
    assert approved.assigned_asset_id is None


def test_reject_marks_task_failed(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g", priority=1)
    task = Task(goal_id=goal.id, description="risky", involves_legal_agreement=True)
    brain.memory.save_task(task)
    brain.tick()

    rejected = brain.reject(task.id)

    assert rejected.status == "failed"


def test_review_produces_a_report(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow monthly revenue", priority=1)
    brain.tick()

    report = brain.review("daily")

    assert report["period"] == "daily"
    assert "tasks_by_status" in report


def test_structural_task_approval_applies_proposal_not_double_dispatch(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("g", priority=1)
    task = Task(goal_id=goal.id, description="recruit a marketing agent", category="recruit_agent")
    brain.memory.save_task(task)
    brain.tick()

    approved = brain.approve(task.id)

    assert approved.status == "done"
    proposals = brain.memory.proposals()
    assert len(proposals) == 1
    assert proposals[0].status == "applied"


def test_review_reallocates_goal_priority_by_founder_estimate(tmp_path):
    brain = _brain(tmp_path)
    strong = Goal(description="strong bet", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak bet", founder_estimate={"expected_revenue": 100.0})
    brain.memory.save_goal(strong)
    brain.memory.save_goal(weak)

    brain.review("daily")

    assert brain.memory.get_goal(strong.id).priority == 1
    assert brain.memory.get_goal(weak.id).priority == 2
    reallocations = [e for e in brain.memory.log() if e.get("kind") == "reallocation"]
    assert {e["goal_id"] for e in reallocations} == {strong.id, weak.id}


def test_review_does_not_re_log_unchanged_reallocation(tmp_path):
    brain = _brain(tmp_path)
    strong = Goal(description="strong bet", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak bet", founder_estimate={"expected_revenue": 100.0})
    brain.memory.save_goal(strong)
    brain.memory.save_goal(weak)

    brain.review("daily")
    first_count = len([e for e in brain.memory.log() if e.get("kind") == "reallocation"])

    brain.review("daily")
    second_count = len([e for e in brain.memory.log() if e.get("kind") == "reallocation"])

    assert second_count == first_count


def test_review_report_surfaces_reallocations(tmp_path):
    brain = _brain(tmp_path)
    strong = Goal(description="strong bet", founder_estimate={"expected_revenue": 1000.0})
    weak = Goal(description="weak bet", founder_estimate={"expected_revenue": 100.0})
    brain.memory.save_goal(strong)
    brain.memory.save_goal(weak)

    report = brain.review("daily")

    assert {r["goal_id"] for r in report["reallocations"]} == {strong.id, weak.id}


def test_recruitment_kpi_attribution_does_not_cross_contaminate_two_goals(tmp_path, monkeypatch):
    from atlas.assets.recruitment_workforce.models import Opportunity
    from atlas.assets.recruitment_workforce.store import WorkforceStore

    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal_a = brain.add_goal("Recruitment engine for goal A", priority=1)
    goal_b = brain.add_goal("Recruitment engine for goal B", priority=1)

    # Pre-seed real intake data so RecruitmentAgent's placeholder-seed path
    # never triggers and adds a confounding third opportunity.
    store = WorkforceStore()
    from atlas.assets.recruitment_workforce.models import EmployerDemand, WorkforceSupplier, CandidateRecord

    supplier = WorkforceSupplier(name="Test Supplier", industry="warehouse_logistics")
    store.save_supplier(supplier)
    store.save_candidate(
        CandidateRecord(industry="warehouse_logistics", description="Worker", pay_rate_expectation_per_hour=18.0)
    )
    store.save_demand(
        EmployerDemand(
            industry="warehouse_logistics",
            employer_name="Existing Employer",
            role="Packer",
            headcount=1,
            rate_expectation_per_hour=30.0,
        )
    )

    # Two already-won opportunities, precisely tagged to distinct goals —
    # simulating that each goal's recruitment initiative already closed.
    store.save_opportunity(
        Opportunity(
            industry="warehouse_logistics",
            employer_demand_id="demand-a",
            stage="won",
            goal_id=goal_a.id,
            task_id="task-a-original",
            recurring_monthly_revenue=1000.0,
            estimated_gross_profit=400.0,
        )
    )
    store.save_opportunity(
        Opportunity(
            industry="warehouse_logistics",
            employer_demand_id="demand-b",
            stage="won",
            goal_id=goal_b.id,
            task_id="task-b-original",
            recurring_monthly_revenue=500.0,
            estimated_gross_profit=300.0,
        )
    )

    task_a = Task(
        goal_id=goal_a.id, description="dispatch for A", category="revenue_recruitment_leads", reversible=True
    )
    task_b = Task(
        goal_id=goal_b.id, description="dispatch for B", category="revenue_recruitment_leads", reversible=True
    )
    brain.memory.save_task(task_a)
    brain.memory.save_task(task_b)

    brain.tick()

    assert brain.kpis.latest(f"revenue_{goal_a.id}") == 1000.0
    assert brain.kpis.latest(f"cost_{goal_a.id}") == 600.0
    assert brain.kpis.latest(f"revenue_{goal_b.id}") == 500.0
    assert brain.kpis.latest(f"cost_{goal_b.id}") == 200.0


def test_recruitment_pipeline_advances_autonomously_then_stops_at_founder_gate(tmp_path, monkeypatch):
    from atlas.assets.recruitment_workforce.store import WorkforceStore

    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = brain.add_goal("Discover and monetize revenue opportunities", priority=1)
    research_task = Task(
        goal_id=goal.id,
        description="Scan for opportunities",
        category="discover_opportunities",
        reversible=True,
    )
    brain.memory.save_task(research_task)

    # No manual task seeding beyond this point — purely autonomous ticking.
    for _ in range(6):
        brain.tick()

    opportunities = [o for o in WorkforceStore().opportunities() if o.goal_id == goal.id]
    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.stage == "proposal_ready"

    recruitment_tasks_before = [t for t in brain.memory.tasks() if t.category == "revenue_recruitment_leads"]

    brain.tick()  # one more tick: must NOT create another continuation task

    recruitment_tasks_after = [t for t in brain.memory.tasks() if t.category == "revenue_recruitment_leads"]
    assert len(recruitment_tasks_after) == len(recruitment_tasks_before)
    assert WorkforceStore().get_opportunity(opportunity.id).stage == "proposal_ready"


def test_affiliate_pipeline_advances_autonomously_then_stops_at_founder_approval(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = brain.add_goal("Grow affiliate revenue")
    seed_task = Task(
        goal_id=goal.id,
        description="Discover affiliate opportunities",
        category="affiliate_pipeline",
        reversible=True,
    )
    brain.memory.save_task(seed_task)

    # No manual task seeding beyond this point — purely autonomous ticking.
    for _ in range(4):
        brain.tick()

    approvals = [t for t in brain.memory.tasks() if t.status == "pending_approval"]
    assert len(approvals) == 1
    approval_task = approvals[0]
    assert approval_task.category == "affiliate_pipeline"
    assert approval_task.source_opportunity_id is not None

    assert brain.kpis.latest(f"expected_revenue_{goal.id}") is not None
    assert brain.kpis.latest(f"risk_score_{goal.id}") is not None
    # Never contaminates the real/measured KPI series
    assert brain.kpis.latest(f"revenue_{goal.id}") is None

    pending_before = {t.id for t in brain.memory.tasks() if t.status == "pending_approval"}
    brain.tick()  # one more tick: must NOT create a second approval request
    pending_after = {t.id for t in brain.memory.tasks() if t.status == "pending_approval"}
    assert pending_after == pending_before


def test_affiliate_intelligence_ranks_and_asks_founder_to_choose(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = brain.add_goal("Find affiliate opportunities")
    seed_task = Task(
        goal_id=goal.id,
        description="Discover affiliate opportunities",
        category="affiliate_intelligence",
        reversible=True,
    )
    brain.memory.save_task(seed_task)

    # No manual task seeding beyond this point — purely autonomous ticking.
    for _ in range(4):
        brain.tick()

    choices = [t for t in brain.memory.tasks() if t.status == "pending_approval"]
    assert len(choices) == 3  # one per ranked opportunity, founder chooses
    assert all(t.category == "affiliate_intelligence" for t in choices)
    assert all(t.source_opportunity_id is not None for t in choices)
    assert any("QuietDesk" in t.description for t in choices)

    assert brain.kpis.latest(f"opportunities_ranked_{goal.id}") == 3.0

    pending_before = {t.id for t in brain.memory.tasks() if t.status == "pending_approval"}
    brain.tick()  # one more tick: must NOT create duplicate choice requests
    pending_after = {t.id for t in brain.memory.tasks() if t.status == "pending_approval"}
    assert pending_after == pending_before


def test_full_affiliate_chain_from_discovery_to_queued_publish_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = brain.add_goal("Find and market an affiliate opportunity")
    seed_task = Task(
        goal_id=goal.id,
        description="Discover affiliate opportunities",
        category="affiliate_intelligence",
        reversible=True,
    )
    brain.memory.save_task(seed_task)

    # Discover -> research -> rank (no manual seeding beyond the one task above).
    for _ in range(4):
        brain.tick()

    choices = [t for t in brain.memory.tasks() if t.status == "pending_approval" and t.category == "affiliate_intelligence"]
    assert len(choices) == 3
    top_choice = max(choices, key=lambda t: "QuietDesk" in t.description)  # QuietDesk ranks first by design

    brain.approve(top_choice.id)
    for t in choices:
        if t.id != top_choice.id:
            brain.reject(t.id)

    # Content Factory generates -> Editorial Review catches the missing
    # affiliate disclosure (revision_required) -> Content Factory fixes just
    # the CTAs -> Editorial Review passes -> founder review requested.
    # Purely autonomous from here.
    for _ in range(8):
        brain.tick()

    reviews = [t for t in brain.memory.tasks() if t.status == "pending_approval" and t.category == "content_factory"]
    assert len(reviews) == 1
    assert "QuietDesk" in reviews[0].description

    opportunity_id = reviews[0].source_opportunity_id
    from atlas.assets.affiliate_department.store import AffiliateStore
    from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH

    opportunity = AffiliateStore(DEFAULT_STORE_PATH).get_opportunity(opportunity_id)
    assert opportunity.stage == "editorial_passed"
    assert opportunity.editorial_verdict == "pass"
    assert opportunity.editorial_cycles == 2  # caught the missing disclosure once, passed on the fix
    assert any("affiliate" in cta.lower() for cta in opportunity.content_package["ctas"])

    brain.approve(reviews[0].id)  # -> approved_for_marketing, synchronously, inside approve()

    # Creative Agent autonomously drafts a brief, but a real creative asset is
    # only ever attached via an explicit founder action (attach_real_asset) --
    # never ticked into existence. Publishing Gateway must not queue without it.
    # (One tick creates the "draft brief" task, a second executes it -- same
    # two-phase bridge timing as every other continuation in this chain.)
    for _ in range(2):
        brain.tick()
    opportunity = AffiliateStore(DEFAULT_STORE_PATH).get_opportunity(opportunity_id)
    assert opportunity.creative_assets["status"] == "brief_ready"

    from atlas.assets.creative_agent.agent import CreativeAgent

    CreativeAgent().attach_real_asset(opportunity_id, "short_video", "file:///real/quietdesk_video.mp4")

    # Publishing Gateway: build -> verify (re-checks editorial PASS, founder
    # approval, disclosure, creative asset) -> READY -> Approve Queue requested.
    # Autonomous from here.
    for _ in range(3):
        brain.tick()

    queue_approvals = [t for t in brain.memory.tasks() if t.status == "pending_approval" and t.category == "publishing_gateway"]
    assert len(queue_approvals) == 1
    assert "Approve Queue" in queue_approvals[0].description
    assert "QuietDesk" in queue_approvals[0].description

    from atlas.assets.publishing_gateway.store import PublishingQueueStore

    package_id = queue_approvals[0].source_opportunity_id
    package = PublishingQueueStore().get_package(package_id)
    assert package.status == "READY"
    assert package.opportunity_id == opportunity_id
    assert "affiliate" in package.affiliate_disclosure.lower()
    assert package.media_references == ["file:///real/quietdesk_video.mp4"]

    brain.approve(queue_approvals[0].id)  # -> APPROVED -> QUEUED, synchronously

    package = PublishingQueueStore().get_package(package_id)
    assert package.status == "QUEUED"

    brain.tick()  # lets the bridge re-snapshot the queue KPI reflecting QUEUED
    report = brain.review("daily")
    assert brain.kpis.latest(f"content_packages_generated_{goal.id}") == 1.0
    assert brain.kpis.latest(f"publish_queue_queued_{goal.id}") == 1.0
    assert report["period"] == "daily"  # Strategist/Reporter pipeline reused unchanged, no new report engine


def test_research_discovers_and_revenue_executes_the_correct_channel(tmp_path, monkeypatch):
    # RecruitmentAgent manages its own pipeline file relative to cwd (it
    # can't receive injected paths through Registry's zero-arg
    # instantiation), so isolate the whole working directory here.
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = brain.add_goal("Discover and monetize revenue opportunities", priority=1)
    research_task = Task(
        goal_id=goal.id,
        description="Scan for opportunities",
        category="discover_opportunities",
        reversible=True,
    )
    brain.memory.save_task(research_task)

    brain.tick()  # research runs; its opportunities are absorbed into new tasks

    tasks = brain.memory.tasks()
    revenue_tasks = [t for t in tasks if t.category.startswith("revenue_")]
    assert len(revenue_tasks) == 2
    assert {t.category for t in revenue_tasks} == {"revenue_affiliate", "revenue_recruitment_leads"}
    assert all(t.status == "proposed" for t in revenue_tasks)

    brain.tick()  # each task is risk-gated, routed to the right agent, and executed

    by_category = {t.category: brain.memory.get_task(t.id) for t in revenue_tasks}
    assert by_category["revenue_affiliate"].assigned_asset_id == "revenue"
    assert by_category["revenue_affiliate"].status == "done"
    assert by_category["revenue_recruitment_leads"].assigned_asset_id == "recruitment_workforce"
    assert by_category["revenue_recruitment_leads"].status == "done"

    research_reloaded = brain.memory.get_task(research_task.id)
    assert research_reloaded.status == "done"
    assert any(h["reason"].startswith("absorbed") for h in research_reloaded.history)


def test_tick_auto_promotes_a_well_evidenced_category_into_a_real_goal_and_dispatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    brain.knowledge.save_finding(
        Finding(source="research", category="digital_product", description="signal 1", evidence="https://example.com/1", evidence_role="direct_assertion")
    )
    brain.knowledge.save_finding(
        Finding(source="research", category="digital_product", description="signal 2", evidence="https://example.com/2", evidence_role="direct_assertion")
    )

    brain.tick()  # advance_intelligence creates the goal+bootstrap task

    goals = [g for g in brain.memory.goals() if g.engine_id == "intelligence_digital_product"]
    assert len(goals) == 1
    tasks = [t for t in brain.memory.tasks() if t.goal_id == goals[0].id]
    assert len(tasks) == 1
    assert tasks[0].category == "revenue_digital_product"
    assert tasks[0].status == "proposed"  # not yet risk-gated/delegated this same tick

    brain.tick()  # next cycle: prioritized, risk-gated, delegated for real

    dispatched = brain.memory.get_task(tasks[0].id)
    assert dispatched.status == "done"
    assert dispatched.assigned_asset_id == "revenue"

    brain.tick()  # a third tick must not create a second goal for the same category
    assert len([g for g in brain.memory.goals() if g.engine_id == "intelligence_digital_product"]) == 1


def test_decision_engine_reopens_only_on_material_evidence_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    brain.knowledge.save_finding(
        Finding(source="research", category="ugc", description="signal 1", evidence="https://example.com/1", evidence_role="direct_assertion")
    )

    brain.tick()  # only 1 independent source: insufficient_evidence, recorded once

    ugc_decisions = [d for d in brain.decisions.decisions() if d.category == "ugc"]
    assert len(ugc_decisions) == 1
    assert ugc_decisions[0].verdict == "insufficient_evidence"

    brain.tick()  # nothing new happened — must NOT log a second, identical Decision
    ugc_decisions = [d for d in brain.decisions.decisions() if d.category == "ugc"]
    assert len(ugc_decisions) == 1

    # Real new evidence arrives — this is what "nothing is permanently
    # true, reopen on material evidence change" actually means in practice.
    brain.knowledge.save_finding(
        Finding(source="research", category="ugc", description="signal 2", evidence="https://example.com/2", evidence_role="direct_assertion")
    )
    brain.tick()  # now 2 independent sources: verdict changes to propose_capability (no ugc channel exists)

    ugc_decisions = sorted((d for d in brain.decisions.decisions() if d.category == "ugc"), key=lambda d: d.created_at)
    assert len(ugc_decisions) == 2
    assert ugc_decisions[0].verdict == "insufficient_evidence"
    assert ugc_decisions[1].verdict == "propose_capability"
    assert ugc_decisions[1].superseded_id == ugc_decisions[0].id  # the reopening is itself traceable


def test_tick_advances_an_in_progress_campaign_execution_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = Goal(description="grow affiliate revenue")
    brain.memory.save_goal(goal)
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira"), categories=["affiliate"])
    brain.influencers.save_influencer(influencer)
    campaign = create_campaign(
        business_objective="launch KetoDNA", category="affiliate", product_offer="KetoDNA",
        influencer_ids=[influencer.id], influencer_registry=brain.influencers, knowledge=brain.knowledge,
        memory=brain.memory, kpis=brain.kpis, registry=brain.campaigns, goal_id=goal.id,
    )
    set_status(campaign.id, "active", brain.campaigns)
    plan = start_execution(campaign.id, brain.campaigns, brain.execution_plans)
    verify_step = plan.steps[0]
    assert verify_step.status == "pending"

    brain.tick()  # CEOBrain's own loop, not a direct orchestrator call — proves the wiring, not just the mechanism

    advanced = brain.execution_plans.get_plan(plan.id)
    verify_step = next(s for s in advanced.steps if s.kind == "verify_readiness")
    assert verify_step.status == "done"


def test_tick_bridges_a_decision_engine_goal_with_a_real_selected_product_into_a_running_campaign(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    # Simulates the real state that would exist after decide() -> invest ->
    # apply_decision() created this goal, and a founder separately picked a
    # real product via the existing, unmodified affiliate_intelligence
    # founder-choice flow (atlas affiliate product add -> approve) — built
    # directly here rather than replaying every intermediate tick of those
    # already-tested pipelines.
    goal = Goal(description="Pursue affiliate opportunities (Decision Engine: 2 independently-sourced findings)", engine_id="intelligence_affiliate")
    brain.memory.save_goal(goal)
    from atlas.assets.affiliate_department.models import AffiliateOpportunity
    brain.affiliate_store.save_opportunity(
        AffiliateOpportunity(
            product_name="KetoDNA", description="a real product", goal_id=goal.id, stage="selected_for_marketing",
            real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        )
    )
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira"), categories=["affiliate"])
    brain.influencers.save_influencer(influencer)
    from atlas.influencer.production import add_template
    from atlas.influencer.registry import add_platform_target, attach_asset
    for kind in ("title", "description", "hook", "cta", "caption_template"):
        add_template(influencer.id, kind, f"{kind}-1", f"real {kind} about {{product_name}} -- AI-curated content. (affiliate link)", brain.influencers)
    attach_asset(influencer.id, "image", "https://example.com/real-asset.jpg", brain.influencers)
    add_platform_target(influencer.id, "YouTube", "@handle", brain.influencers)

    brain.tick()

    campaigns = brain.campaigns.campaigns()
    assert len(campaigns) == 1
    campaign = campaigns[0]
    assert campaign.goal_id == goal.id
    assert campaign.product_offer == "KetoDNA"
    assert campaign.influencer_ids == [influencer.id]
    assert campaign.status == "active"

    plans = brain.execution_plans.plans_for_campaign(campaign.id)
    assert len(plans) == 1
    review_step = next(s for s in plans[0].steps if s.kind == "request_founder_review")
    assert review_step.status == "dispatched"  # cascaded automatically through every internal stage, then stopped at the founder-approval boundary

    # The old opportunity-driven content chain must NOT have also picked up
    # this same real opportunity — that's the whole point of the guard.
    content_factory_tasks = [t for t in brain.memory.tasks() if t.category == "content_factory"]
    assert content_factory_tasks == []


def test_approved_campaign_review_task_dispatches_to_the_real_campaign_execution_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = Goal(description="Pursue affiliate opportunities (Decision Engine: 2 independently-sourced findings)", engine_id="intelligence_affiliate")
    brain.memory.save_goal(goal)
    from atlas.assets.affiliate_department.models import AffiliateOpportunity
    brain.affiliate_store.save_opportunity(
        AffiliateOpportunity(
            product_name="KetoDNA", description="a real product", goal_id=goal.id, stage="selected_for_marketing",
            real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        )
    )
    influencer = DigitalInfluencer(identity=IdentityProfile(name="Mira"), categories=["affiliate"])
    brain.influencers.save_influencer(influencer)
    from atlas.influencer.production import add_template
    from atlas.influencer.registry import add_platform_target, attach_asset
    for kind in ("title", "description", "hook", "cta", "caption_template"):
        add_template(influencer.id, kind, f"{kind}-1", f"real {kind} about {{product_name}} -- AI-curated content. (affiliate link)", brain.influencers)
    attach_asset(influencer.id, "image", "https://example.com/real-asset.jpg", brain.influencers)
    add_platform_target(influencer.id, "YouTube", "@handle", brain.influencers)
    brain.tick()

    campaign = brain.campaigns.campaigns()[0]
    plan = brain.execution_plans.plans_for_campaign(campaign.id)[0]
    review_step = next(s for s in plan.steps if s.kind == "request_founder_review")

    approved = brain.approve(review_step.task_id)
    assert approved.status == "delegated"
    assert approved.assigned_asset_id == "campaign_execution"  # matched by category, not an arbitrary fallback asset

    brain.tick()  # Monitor.sync() resolves "delegated" -> "done" on the next cycle, same as every other task

    resolved = brain.memory.get_task(review_step.task_id)
    assert resolved.status == "done"
    # The real, intentional asset handled it — not an arbitrary Triggerable
    # fallback (the bug this asset exists to fix) — and its report()
    # honestly reflects the real, still-active campaign (report() is
    # necessarily aggregate/task-agnostic, the same shape every other
    # asset's report() already has — it can't echo back run()'s
    # per-task next_step message, which is available immediately at
    # dispatch time instead).
    assert resolved.assigned_asset_id == "campaign_execution"
    assert campaign.id in resolved.history[-1]["reason"]


def test_tick_leaves_the_old_content_factory_chain_untouched_when_no_influencer_is_registered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    goal = Goal(description="Pursue affiliate opportunities", engine_id="intelligence_affiliate")
    brain.memory.save_goal(goal)
    from atlas.assets.affiliate_department.models import AffiliateOpportunity
    brain.affiliate_store.save_opportunity(
        AffiliateOpportunity(product_name="KetoDNA", description="a real product", goal_id=goal.id, stage="selected_for_marketing")
    )
    # no influencer registered for "affiliate" — the new bridge must leave this alone

    brain.tick()

    assert brain.campaigns.campaigns() == []
    # falls through to the old pipeline exactly as it always has
    content_factory_tasks = [t for t in brain.memory.tasks() if t.category == "content_factory"]
    assert len(content_factory_tasks) == 1


# --- Connectivity Bridge Integration (docs/DESIGN_BRIDGE_INTEGRATION.md,
# 2026-08-11) -- the real wiring of Bridges 1-3 into tick(). Every other
# test above already exercises tick() with real Findings that have no
# `subject` set, and continues to pass unchanged -- proof this integration
# is additive, not a behavior change to anything pre-existing.


def test_tick_wires_bridge_1_creates_a_real_opportunity_from_sourced_findings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    brain.knowledge.save_finding(
        Finding(
            source="research", category="digital_product", subject="AI Course Bundle",
            description="signal 1", evidence="https://example.com/1", evidence_role="direct_assertion",
        )
    )
    brain.knowledge.save_finding(
        Finding(
            source="research", category="digital_product", subject="AI Course Bundle",
            description="signal 2", evidence="https://example.com/2", evidence_role="direct_assertion",
        )
    )

    brain.tick()

    opportunities = brain.opportunities.by_category("digital_product")
    assert len(opportunities) == 1
    assert opportunities[0].subject == "AI Course Bundle"
    assert opportunities[0].stage == "discovered"
    assert len(opportunities[0].evidence_finding_ids) == 2


def test_tick_wires_bridges_2_and_3_boosts_the_reasoning_preferred_categorys_real_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brain = _brain(tmp_path)
    # digital_product: 3 independent real sources -- the stronger real
    # evidence, so Bridge 2 must prefer this Opportunity over ugc's below.
    for i in range(3):
        brain.knowledge.save_finding(
            Finding(
                source="research", category="digital_product", subject="AI Course Bundle",
                description=f"signal {i}", evidence=f"https://example.com/dp{i}", evidence_role="direct_assertion",
            )
        )
    # ugc: only 2 independent real sources -- still clears
    # MIN_INDEPENDENT_SOURCES (so it still gets a real Decision/Task), but
    # weaker real evidence than digital_product's, deterministically.
    for i in range(2):
        brain.knowledge.save_finding(
            Finding(
                source="research", category="ugc", subject="Daily Vlog Series",
                description=f"signal {i}", evidence=f"https://example.com/ugc{i}", evidence_role="direct_assertion",
            )
        )

    brain.tick()

    dp_decision = next(d for d in brain.decisions.decisions() if d.category == "digital_product")
    ugc_decision = next(d for d in brain.decisions.decisions() if d.category == "ugc")
    assert dp_decision.verdict == "invest"  # real channel exists
    assert ugc_decision.verdict == "propose_capability"  # no real channel exists -- unchanged by Bridge 3

    dp_goal = brain.memory.get_goal(dp_decision.goal_id)
    ugc_goal = brain.memory.get_goal(ugc_decision.goal_id)
    dp_task = next(t for t in brain.memory.tasks() if t.goal_id == dp_goal.id)
    ugc_task = next(t for t in brain.memory.tasks() if t.goal_id == ugc_goal.id)

    # Bridge 2 (stronger real evidence: 3 sources vs. 2) preferred
    # digital_product -- Bridge 3 made that observable as a real priority
    # boost on its real Task, and left ugc's real Task untouched.
    from atlas.brain.decision_priority_advance import REASONING_PRIORITY_BOOST
    assert dp_task.priority_score == REASONING_PRIORITY_BOOST
    assert ugc_task.priority_score == 0.0

    # "Bridge may influence, but never decide" -- the real verdicts
    # themselves are exactly what decide() alone would have produced,
    # completely unaffected by which Opportunity Reasoning preferred.
    assert dp_decision.verdict == "invest"
    assert ugc_decision.verdict == "propose_capability"


def test_milestone3_committed_opportunity_reaches_real_campaign_via_business_plan_bridge(tmp_path, monkeypatch):
    # End-to-end proof of Milestone 4 (Business Plan Generator) wired into
    # the real tick() loop -- and, critically, the real fix for the
    # ALWAYS_REQUIRES_APPROVAL gap found during this Milestone's own
    # Implementation: approve() must actually reach task.status=="done" via
    # a real linked Proposal, not the risky Registry-matching fallback.
    from atlas.brain.business_plan_advance import COMMERCIAL_TERMS_TASK_CATEGORY, create_affiliate_opportunity_from_terms

    monkeypatch.chdir(tmp_path)
    # This dev machine's persistent environment has
    # ATLAS_OPPORTUNITY_DISCOVERY_V1=1 set. opportunity_discovery_advance.py
    # is no longer called from tick() at all (2026-08-13, Design §7 --
    # "one road, not an interchange"), so it can no longer race this bridge
    # regardless of the flag. The flag still has one real, independent
    # effect inside this same tick() call -- decision_apply.py's
    # OPPORTUNITY_DISCOVERY_BOOTSTRAP_OVERRIDES, which decides whether the
    # old category-level "invest" path bootstraps into affiliate_pipeline
    # or affiliate_intelligence -- so the flag is still controlled
    # explicitly here for determinism, not because of any remaining race.
    monkeypatch.delenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", raising=False)
    brain = _brain(tmp_path)
    brain.influencers.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Mira", market="US"), categories=["affiliate"]))

    # Two real, independent findings -- crosses MIN_INDEPENDENT_SOURCES in
    # the very first tick, so Bridge 1 creates the Universal Core
    # Opportunity and Milestone 3 commits it in that same tick.
    brain.knowledge.save_finding(Finding(source="research", category="affiliate", subject="KetoDNA", description="e1", evidence="https://e1", evidence_role="direct_assertion"))
    brain.knowledge.save_finding(Finding(source="research", category="affiliate", subject="KetoDNA", description="e2", evidence="https://e2", evidence_role="direct_assertion"))

    brain.tick()  # Bridge 1 creates the Opportunity; Milestone 3 commits it; Milestone 4 creates the commercial-terms Task

    committed = [o for o in brain.opportunities.opportunities() if o.subject == "KetoDNA"]
    assert len(committed) == 1
    assert committed[0].goal_id is not None

    terms_tasks = [t for t in brain.memory.tasks() if t.category == COMMERCIAL_TERMS_TASK_CATEGORY]
    assert len(terms_tasks) == 1
    terms_task = terms_tasks[0]
    assert terms_task.source_opportunity_id == committed[0].id
    assert terms_task.status == "proposed"  # not yet risk-gated this tick

    brain.tick()  # risk-gates the new task -- real linked Proposal created, task -> pending_approval

    terms_task = brain.memory.get_task(terms_task.id)
    assert terms_task.status == "pending_approval"
    linked_proposals = [p for p in brain.memory.proposals() if p.task_id == terms_task.id]
    assert len(linked_proposals) == 1
    assert linked_proposals[0].status == "pending_approval"

    brain.approve(terms_task.id)  # closes the real linked Proposal

    terms_task = brain.memory.get_task(terms_task.id)
    assert terms_task.status == "done"

    opportunity = create_affiliate_opportunity_from_terms(
        terms_task.id, brain.memory, brain.opportunities, brain.affiliate_store,
        commission_per_conversion=25.0, real_affiliate_link="https://www.digistore24.com/redir/123456/myaffid/",
        provider="digistore24",
    )
    assert opportunity.stage == "selected_for_marketing"

    brain.tick()  # campaign_advance.py (unmodified) picks up selected_for_marketing -> real Campaign

    real_campaigns = [c for c in brain.campaigns.campaigns() if c.goal_id == committed[0].goal_id]
    assert len(real_campaigns) == 1
    assert real_campaigns[0].product_offer == "KetoDNA"
    assert real_campaigns[0].status == "active"


def test_default_registry_wires_video_research_to_this_brains_own_knowledge(tmp_path):
    """Video Research must write into the CEOBrain's ONE shared KnowledgeBase,
    never a silently-created default .atlas/knowledge.json of its own."""
    kb = KnowledgeBase(tmp_path / "knowledge.json")
    brain = CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        knowledge=kb,
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
        campaigns=CampaignRegistry(tmp_path / ".atlas" / "campaigns.json"),
        influencers=InfluencerRegistry(tmp_path / ".atlas" / "influencers.json"),
        execution_plans=ExecutionPlanRegistry(
            tmp_path / ".atlas" / "execution_plans.json"
        ),
        affiliate_store=AffiliateStore(
            tmp_path / ".atlas" / "affiliate_intelligence.json"
        ),
    )

    video_instance = brain.registry._instance("video_research")

    assert video_instance._knowledge is kb
    assert video_instance._knowledge is brain.knowledge


def test_tick_calls_video_research_bridge_with_this_brains_shared_state(
    tmp_path,
    monkeypatch,
):
    """Production wiring qualification: CEOBrain.tick really reaches the
    bridge with its own Memory/Knowledge/KPI objects. The bridge itself is
    replaced here so this test can never perform a YouTube/Gemini call."""
    import atlas.brain.ceo as ceo_module

    calls = []

    def fake_advance_video_research(memory, knowledge, kpis):
        calls.append((memory, knowledge, kpis))
        return []

    monkeypatch.setattr(
        ceo_module,
        "advance_video_research",
        fake_advance_video_research,
    )

    brain = _brain(tmp_path)
    brain.tick()

    assert len(calls) == 1
    memory, knowledge, kpis = calls[0]
    assert memory is brain.memory
    assert knowledge is brain.knowledge
    assert kpis is brain.kpis



def test_tick_wires_layer2_with_start_of_tick_finding_baseline(
    tmp_path,
    monkeypatch,
):
    """Stage 7 Layer-2 production wiring qualification.

    The real bridge is replaced so this test can never spend an AI call.
    Proves CEOBrain snapshots pre-existing Findings before tick work and
    passes its own shared Memory/Knowledge objects into Layer 2.
    """
    import atlas.brain.ceo as ceo_module

    monkeypatch.setattr(
        ceo_module,
        "pattern_hypothesis_enabled",
        lambda: True,
    )

    calls = []

    def fake_advance_pattern_hypotheses(
        memory,
        knowledge,
        *,
        baseline_finding_ids=None,
        ai_provider=None,
    ):
        calls.append(
            (
                memory,
                knowledge,
                baseline_finding_ids,
            )
        )
        return []

    monkeypatch.setattr(
        ceo_module,
        "advance_pattern_hypotheses",
        fake_advance_pattern_hypotheses,
    )

    brain = _brain(tmp_path)

    existing = Finding(
        source="research",
        category="affiliate",
        description="pre-existing evidence",
        evidence="https://example.com/preexisting",
        evidence_role="direct_assertion",
    )
    brain.knowledge.save_finding(existing)

    brain.tick()

    assert len(calls) == 1
    memory, knowledge, baseline_ids = calls[0]
    assert memory is brain.memory
    assert knowledge is brain.knowledge
    assert baseline_ids == {existing.id}
