from atlas.brain.ceo import CEOBrain
from atlas.brain.decisions import DecisionLog
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Task
from atlas.core.registry import Registry
from atlas.core.store import JSONStore


def _brain(tmp_path):
    return CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
        knowledge=KnowledgeBase(tmp_path / "knowledge.json"),
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
    )


def test_tick_delegates_a_new_goal_to_a_capable_fallback_asset(tmp_path):
    # Category "analyze_revenue" matches no asset's declared categories, so
    # this falls to Delegator's unmatched-fallback path (first Triggerable
    # asset that accepts it, in id order) — which asset that is depends on
    # what's registered, not a specific business rule that it must be MAYA.
    brain = _brain(tmp_path)
    brain.add_goal("Grow monthly revenue", priority=1)

    tasks = brain.tick()

    assert len(tasks) == 1
    assert tasks[0].assigned_asset_id is not None
    assert tasks[0].status in ("delegated", "done")


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

    assert approved.status in ("delegated", "done")
    assert approved.assigned_asset_id is not None  # unmatched-category fallback, not a specific-asset business rule


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
        Finding(source="research", category="digital_product", description="signal 1", evidence="https://example.com/1")
    )
    brain.knowledge.save_finding(
        Finding(source="research", category="digital_product", description="signal 2", evidence="https://example.com/2")
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
        Finding(source="research", category="ugc", description="signal 1", evidence="https://example.com/1")
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
        Finding(source="research", category="ugc", description="signal 2", evidence="https://example.com/2")
    )
    brain.tick()  # now 2 independent sources: verdict changes to propose_capability (no ugc channel exists)

    ugc_decisions = sorted((d for d in brain.decisions.decisions() if d.category == "ugc"), key=lambda d: d.created_at)
    assert len(ugc_decisions) == 2
    assert ugc_decisions[0].verdict == "insufficient_evidence"
    assert ugc_decisions[1].verdict == "propose_capability"
    assert ugc_decisions[1].superseded_id == ugc_decisions[0].id  # the reopening is itself traceable
