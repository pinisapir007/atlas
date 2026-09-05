from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.assets.affiliate_intelligence.agent import DEFAULT_STORE_PATH as AFFILIATE_INTELLIGENCE_STORE_PATH
from atlas.assets.research_discovery.agent import ResearchDiscoveryAgent
from atlas.assets.video_research.agent import VideoResearchAgent
from atlas.brain.affiliate_intelligence_advance import advance_affiliate_intelligence
from atlas.brain.affiliate_pipeline_advance import advance_affiliate_pipeline
from atlas.brain.business_plan_advance import advance_business_plan_generation
from atlas.brain.campaign_advance import advance_decision_driven_campaigns
from atlas.brain.content_factory_advance import advance_content_factory
from atlas.brain.conversation_memory import ConversationMemory
from atlas.brain.creative_agent_advance import advance_creative_agent
from atlas.brain.decision_apply import apply_decision, supersede_pending_capability_proposals
from atlas.brain.decision_engine import has_materially_changed
from atlas.brain.decisions import DecisionLog
from atlas.brain.deep_research_advance import advance_deep_research
from atlas.brain.discovery.decide import advance_executive_discovery, decide_all_with_discovery
from atlas.brain.delegator import Delegator, is_structural
from atlas.brain.editorial_review_advance import advance_editorial_review
from atlas.brain.feature_flags import pattern_hypothesis_enabled
from atlas.brain.publishing_gateway_advance import advance_publishing_gateway
from atlas.brain.improvement import propose_improvements
from atlas.brain.intake import absorb_opportunities
from atlas.brain.intelligence_cycle_advance import advance_intelligence_cycle
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.investigation_advance import advance_investigations
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.kpi_intake import record_revenue
from atlas.brain.ledger import Ledger
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_investigation_advance import advance_marketplace_investigations
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Decision, Goal, Task, now
from atlas.brain.monitor import Monitor
from atlas.brain.decision_priority_advance import apply_reasoning_priority
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.pattern_hypothesis_advance import advance_pattern_hypotheses
from atlas.brain.opportunity_advance import advance_opportunities_from_findings
from atlas.brain.pipeline_advance import advance_recruitment_pipeline
from atlas.brain.planner import Planner, SimplePlanner
from atlas.brain.prioritizer import Prioritizer, SimplePrioritizer
from atlas.brain.reasoning_advance import advance_opportunity_comparisons
from atlas.brain.reporter import Reporter
from atlas.brain.research_mission_advance import advance_research_missions
from atlas.brain.research_mission_source_advance import advance_research_mission_sources
from atlas.brain.research_mission_youtube_advance import advance_research_mission_youtube
from atlas.brain.research_missions import ResearchMissionStore
from atlas.brain.revenue_strategy import commit_ready_opportunities
from atlas.brain.sales_sync import advance_sales_sync
from atlas.brain.risk import RiskPolicy
from atlas.brain.tick_lock import TickAlreadyRunning, tick_lock
from atlas.brain.video_research_advance import advance_video_research
from atlas.brain.strategist import SimpleStrategist, Strategist
from atlas.brand.registry import BrandRegistry
from atlas.campaign.registry import CampaignRegistry
from atlas.core.registry import Registry
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.orchestrator import advance_all_campaign_executions
from atlas.orchestrator.registry import ExecutionPlanRegistry

OPEN_FOR_PRIORITIZATION = {"proposed", "prioritized"}


class CEOBrain:
    """Ties planning, prioritization, risk-gating, delegation, and
    monitoring into ATLAS's two operating cycles.

    tick(): the frequent operational loop — plan, prioritize, risk-gate,
    delegate, monitor. review(period): the slow strategic loop — evidence-
    gated redesign proposals, applied-redesign outcome evaluation, and the
    daily/weekly/monthly executive report.
    """

    def __init__(
        self,
        memory: BrainMemory | None = None,
        registry: Registry | None = None,
        planner: Planner | None = None,
        prioritizer: Prioritizer | None = None,
        risk_policy: RiskPolicy | None = None,
        reporter: Reporter | None = None,
        strategist: Strategist | None = None,
        knowledge: KnowledgeBase | None = None,
        decisions: DecisionLog | None = None,
        ledger: Ledger | None = None,
        campaigns: CampaignRegistry | None = None,
        influencers: InfluencerRegistry | None = None,
        brands: BrandRegistry | None = None,
        execution_plans: ExecutionPlanRegistry | None = None,
        affiliate_store: AffiliateStore | None = None,
        conversations: ConversationMemory | None = None,
        opportunities: OpportunityStore | None = None,
        marketplace_catalog: MarketplaceCatalogStore | None = None,
        investigations: InvestigationStore | None = None,
        research_missions: ResearchMissionStore | None = None,
        intelligence_index: IntelligenceIndex | None = None,
    ):
        self.memory = memory if memory is not None else BrainMemory()
        # knowledge must exist before the default Registry is built, below --
        # it's the real fix for Qualification Run #1's root cause
        # (docs/QUALIFICATION_RUN_2026-08-11.md, gap #7): Registry._instance()
        # has no way to pass real constructor arguments to a lazily-imported
        # asset, so research_discovery previously always fell back to its own
        # default (real, relative ".atlas/knowledge.json") KnowledgeBase --
        # never the one this CEOBrain actually reads from. Pre-seeding it here
        # via Registry(instances=...) is the minimal fix: only reached when
        # `registry` itself isn't explicitly provided (an explicitly-passed
        # Registry is never silently mutated -- the caller configured it on
        # purpose, e.g. every existing test in test_ceo.py).
        self.knowledge = knowledge if knowledge is not None else KnowledgeBase()
        self.intelligence_index = (
            intelligence_index
            if intelligence_index is not None
            else IntelligenceIndex()
        )
        self.registry = (
            registry
            if registry is not None
            else Registry(
                instances={
                    "research_discovery": ResearchDiscoveryAgent(
                        knowledge=self.knowledge
                    ),
                    "video_research": VideoResearchAgent(
                        knowledge=self.knowledge
                    ),
                }
            )
        )
        self.planner = planner if planner is not None else SimplePlanner()
        self.prioritizer = prioritizer if prioritizer is not None else SimplePrioritizer()
        self.risk_policy = risk_policy if risk_policy is not None else RiskPolicy()
        self.reporter = reporter if reporter is not None else Reporter()
        self.strategist = strategist if strategist is not None else SimpleStrategist()
        self.decisions = decisions if decisions is not None else DecisionLog()
        self.ledger = ledger if ledger is not None else Ledger()
        # ".atlas/affiliate_intelligence.json" — the shared store file
        # AffiliateIntelligenceAgent/ContentFactoryAgent/EditorialReviewAgent/
        # CreativeAgent/PublishingGatewayAgent all already use, and the only
        # place "selected_for_marketing" is ever set (see
        # campaign_advance.py) — not affiliate_department.json's own
        # default, a different file for the separate, placeholder-discovery
        # chain that never reaches that stage.
        self.affiliate_store = affiliate_store if affiliate_store is not None else AffiliateStore(AFFILIATE_INTELLIGENCE_STORE_PATH)
        self.campaigns = campaigns if campaigns is not None else CampaignRegistry()
        self.influencers = influencers if influencers is not None else InfluencerRegistry()
        self.brands = brands if brands is not None else BrandRegistry()
        self.execution_plans = execution_plans if execution_plans is not None else ExecutionPlanRegistry()
        self.conversations = conversations if conversations is not None else ConversationMemory()
        # docs/DESIGN_BRIDGE_INTEGRATION.md — the same optional-with-default
        # pattern as knowledge/decisions/ledger, used here for the first time
        # by Bridges 1-3 wired into tick() below.
        self.opportunities = opportunities if opportunities is not None else OpportunityStore()
        # ONE BRAIN Production Wiring (2026-08-17): both default to their
        # own real, empty stores when unset -- a brain with no Marketplace
        # activity yet reads an empty catalog/investigations file and the
        # bridges below simply do nothing, unchanged from today's behavior.
        self.marketplace_catalog = marketplace_catalog if marketplace_catalog is not None else MarketplaceCatalogStore()
        self.investigations = investigations if investigations is not None else InvestigationStore()

        # Durable Research Mission orchestration store. Construction and
        # empty reads are side-effect-free, so the default store does not
        # create .atlas/research_missions.json merely because CEOBrain
        # exists. All three advance bridges are independently feature-gated
        # and therefore remain exact no-ops while Research Mission is off.
        self.research_missions = (
            research_missions
            if research_missions is not None
            else ResearchMissionStore()
        )

        self.kpis = KPIRegistry(self.memory)
        self.delegator = Delegator(self.memory)
        self.monitor = Monitor()
        # In-memory only, never persisted -- see intelligence_cycle_advance.py
        # for why no new durable store was added in this pass.
        self.last_intelligence_workflow_results: list = []

    def add_goal(
        self,
        description: str,
        priority: int = 3,
        horizon: str = "short",
        founder_estimate: dict | None = None,
    ) -> Goal:
        goal = Goal(
            description=description,
            priority=priority,
            horizon=horizon,
            founder_estimate=founder_estimate or {},
        )
        self.memory.save_goal(goal)
        return goal

    def tick(self) -> list[Task]:
        """Real entry point every real caller (Scheduler, CLI, a future
        API, a manual call) goes through -- the application-level Tick
        Lock (P0 Stage 2A, tick_lock.py) lives exactly here, not in any
        one caller, so it protects all of them uniformly and can never
        be forgotten at a new call site. A real, live tick already in
        progress is never a crash: it's logged durably
        (BrainMemory.append_log, the same append-only outcome log
        recent_activity()/review() already read) and this call returns
        an honest empty result, the same "documented, honest no-op"
        shape every other real skip condition in this codebase already
        uses."""
        lock_path = self.memory.path.parent / "tick.lock"
        try:
            with tick_lock(lock_path):
                return self._tick_impl()
        except TickAlreadyRunning as exc:
            self.memory.append_log({"at": now(), "event": "tick_skipped_lock_contention", "reason": str(exc)})
            return []

    def _tick_impl(self) -> list[Task]:
        # Stage 7 / Layer 2 baseline snapshot. Taken before ANY tick work
        # can create new Findings. Only needed when the feature is enabled;
        # disabled production keeps zero Layer-2 KnowledgeBase scan here.
        layer2_baseline_finding_ids = (
            {finding.id for finding in self.knowledge.findings()}
            if pattern_hypothesis_enabled()
            else None
        )

        goals = self.memory.goals()
        tasks = self.memory.tasks()

        # Autonomous Revenue / Sales Sync V2. The bridge itself is
        # feature-flag gated and makes zero provider calls while disabled.
        # Runs before planning/decision work so newly verified revenue or
        # reversals are visible to this same tick's reasoning.
        advance_sales_sync(goals, self.kpis, self.ledger)

        new_tasks = self.planner.plan(goals, tasks)
        for task in new_tasks:
            self.memory.save_task(task)
        tasks = tasks + new_tasks

        open_tasks = [t for t in tasks if t.status in OPEN_FOR_PRIORITIZATION]
        goals_by_id = {g.id: g for g in goals}
        self.prioritizer.score(open_tasks, goals_by_id)
        open_tasks.sort(key=lambda t: t.priority_score, reverse=True)

        for task in open_tasks:
            self._risk_gate_and_delegate(task)
            self.memory.save_task(task)

        self.monitor.sync(self.memory.tasks(), self.registry, self.memory, self.kpis)

        # Research Mission orchestration.
        #
        # Ordering is deliberate:
        # 1. Monitor above reconciles any video_research Task that finished
        #    during the previous dispatch lifecycle.
        # 2. Generic concrete sources may create durable Findings.
        # 3. YouTube reconciles those normal Task results or creates at most
        #    one existing video_research Task for a pending YouTube source.
        # 4. Lifecycle closure runs last so a Mission cannot close before
        #    every source had this tick's opportunity to advance.
        #
        # The bridges themselves own their feature gates. With
        # ATLAS_RESEARCH_MISSION_ENABLED unset this entire sequence is an
        # exact no-op and does not create the ResearchMissionStore file.
        advance_research_mission_sources(
            self.research_missions,
            self.knowledge,
        )
        advance_research_mission_youtube(
            self.research_missions,
            self.memory,
            self.knowledge,
        )
        advance_research_missions(
            self.research_missions,
        )

        for opportunity_task in absorb_opportunities(self.memory.tasks(), self.registry, self.memory, self.knowledge):
            self.memory.save_task(opportunity_task)

        # Executive Discovery's Research Trigger (Mechanism 2, docs/
        # EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md) -- runs before
        # _decide_and_apply() so a category the breadth gate flags this
        # same tick can start accumulating real evidence as soon as
        # possible, not one tick late. Purely additive: dispatches real,
        # auto-delegating research Tasks, never touches Goal/Decision
        # state itself.
        advance_executive_discovery(self.knowledge, self.memory, self.kpis)

        # Executive Discovery -> Video Research source bridge. Deliberately
        # separate from ResearchDiscoveryAgent: when its own feature flag is
        # off this is an inert no-op; when enabled it may create at most one
        # bounded video_research Task for the normal next-tick delegation
        # lifecycle. It never performs Gemini video understanding here.
        advance_video_research(self.memory, self.knowledge, self.kpis)

        # Shallow -> Deep Research Escalation (P0 Independence Mission,
        # 2026-08-18) -- runs immediately after the shallow trigger above
        # so a category that just became research_exhausted() this same
        # tick is escalated without waiting a tick, the same
        # same-tick-visibility discipline advance_decision_driven_campaigns()
        # -> advance_content_factory() already established. Inherits
        # Executive Discovery's own ATLAS_EXECUTIVE_DISCOVERY_ENABLED gate
        # (a no-op in real production until that's explicitly turned on).
        advance_deep_research(self.memory, self.knowledge, self.kpis)

        # ONE BRAIN Production Wiring (2026-08-17): Marketplace -> Investigation
        # -> Bridge 1, closing the confirmed-disconnected arrow from the
        # production-wiring audit. Both bridges only ever read already-
        # persisted, local-disk state (MarketplaceCatalogStore/
        # InvestigationStore) -- zero browser/network/CDP calls, safe to run
        # unconditionally every tick, exactly like every other *_advance.py
        # bridge below. `source_refs={}` (no autonomous URL-selection
        # mechanism exists yet, by design -- see investigation_advance.py's
        # own docstring): every real Investigation this creates honestly
        # stays "waiting_for_evidence" until a real, approved source_ref is
        # supplied through a future, separate mechanism -- never invented,
        # never a false advancement, never an exception that could fail
        # this tick.
        advance_marketplace_investigations(self.marketplace_catalog, self.knowledge, self.investigations)
        advance_investigations(self.investigations, self.knowledge, source_refs={})

        # Stage 7 / Layer 2 autonomous Pattern/Hypothesis Formation.
        # Feature-flagged OFF by default and internally bounded to one
        # category per tick. It writes Claim knowledge/audit markers only:
        # never Tasks, Goals, Decisions, dispatch, spending, or publishing.
        # The start-of-tick baseline above lets the first enabled tick
        # distinguish historical evidence from Findings genuinely created
        # during this tick.
        advance_pattern_hypotheses(
            self.memory,
            self.knowledge,
            baseline_finding_ids=layer2_baseline_finding_ids,
        )

        # Connectivity Bridges 1-3 (docs/DESIGN_BRIDGE_INTEGRATION.md,
        # 2026-08-11) -- integration only, zero new judgment anywhere in
        # this block ("Integration never owns behavior"). Order is forced,
        # not chosen: Bridge 1 needs this tick's real Findings (already
        # accumulated above); Bridge 2 needs Bridge 1's updated
        # OpportunityStore; Bridge 3 needs both Bridge 2's real comparisons
        # and _decide_and_apply()'s real (Decision, Task) pairs. Every
        # bridge stays independently callable/testable -- this is only a
        # call sequence, never a merge into one mechanism.
        advance_opportunities_from_findings(self.knowledge, self.opportunities)
        comparisons = advance_opportunity_comparisons(self.opportunities)

        decisions_and_tasks = self._decide_and_apply()

        opportunities_by_id = {o.id: o for o in self.opportunities.opportunities()}
        for boosted_task in apply_reasoning_priority(decisions_and_tasks, comparisons, opportunities_by_id):
            # apply_reasoning_priority() mutates the real Task object it was
            # given in place -- _decide_and_apply() already persisted that
            # same Task once, above, before its priority_score was boosted,
            # and self.memory round-trips through real JSON storage (no
            # shared object identity across separate reads), so the boost
            # is only real/observable once re-saved here.
            self.memory.save_task(boosted_task)

        # Milestone 3 (Revenue Strategy) -- runs after _decide_and_apply()
        # above so a category-level Goal apply_decision() creates this same
        # tick is already visible to commit_ready_opportunities()'s own
        # goals_touching_category() join-before-create check, not one tick
        # late. Scoped to "affiliate" -- the one category Milestone 4's own
        # bridge below can actually reach a real Campaign for; not a
        # decision about any other category. commit_ready_opportunities()
        # is fully self-contained (saves its own Goals/Tasks/Opportunities),
        # so nothing further is done with its return value here.
        commit_ready_opportunities("affiliate", self.opportunities, self.knowledge, self.memory)

        # Runs the real, unmodified 8-stage intelligence workflow for every
        # Goal the Decision Engine step just above created (or created on an
        # earlier tick) -- the minimum bridge connecting the engine layer
        # (Intelligence/Research/Resource/Opportunity/Time/Execution
        # Planning) to the automatic tick loop. Read-only: does not create
        # or dispatch anything. See intelligence_cycle_advance.py.
        self.last_intelligence_workflow_results = advance_intelligence_cycle(
            self.memory,
            self.knowledge,
            self.kpis,
            self.intelligence_index,
        )

        for continuation_task in advance_recruitment_pipeline(self.memory.tasks(), self.registry, self.memory):
            self.memory.save_task(continuation_task)

        for affiliate_task in advance_affiliate_pipeline(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(affiliate_task)

        # advance_opportunity_discovery() (opportunity_discovery_advance.py)
        # deliberately no longer called here (2026-08-13, Milestone 4
        # Qualification -- docs/DESIGN_BUSINESS_PLAN_GENERATOR.md §7): a full
        # functional comparison found no real business capability unique to
        # it that Milestone 3 + this bridge don't already cover, and it had
        # its own structural defect (could reach selected_for_marketing with
        # permanently-empty commercial terms). "One road, not an
        # interchange" -- the function itself, opportunity_ranking.
        # rank_opportunities() (6 other real callers), and
        # feature_flags.opportunity_discovery_v1_enabled() (2 other
        # independent uses) are all deliberately untouched.
        for intelligence_task in advance_affiliate_intelligence(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(intelligence_task)

        # Milestone 4 (Business Plan Generator) -- bridges a Milestone-3-
        # committed Universal Core Opportunity to a real AffiliateOpportunity
        # request, the same real "selected_for_marketing" entry point
        # advance_decision_driven_campaigns() below already reads. Runs
        # after commit_ready_opportunities() above (so a Goal committed this
        # same tick is already visible) and before the campaign bridge below
        # (so a same-tick approval could -- once the founder later supplies
        # terms -- be picked up as soon as possible).
        for terms_task in advance_business_plan_generation(self.memory, self.opportunities, self.affiliate_store):
            self.memory.save_task(terms_task)

        advance_decision_driven_campaigns(
            self.memory, self.knowledge, self.kpis, self.influencers, self.campaigns, self.execution_plans,
            self.affiliate_store, self.brands,
        )

        # advance_decision_driven_campaigns() runs first (above) so a goal
        # it claims this same tick is already reflected in self.campaigns
        # by the time this reads it — the exact ordering that keeps the
        # old opportunity-driven chain and the new Campaign pipeline from
        # both picking up the same newly-selected_for_marketing opportunity.
        claimed_goal_ids = {c.goal_id for c in self.campaigns.campaigns() if c.goal_id}
        for content_task in advance_content_factory(self.memory.tasks(), self.registry, self.memory, self.kpis, claimed_goal_ids):
            self.memory.save_task(content_task)

        for editorial_task in advance_editorial_review(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(editorial_task)

        for creative_task in advance_creative_agent(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(creative_task)

        for publishing_task in advance_publishing_gateway(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(publishing_task)

        advance_all_campaign_executions(self.execution_plans, self.campaigns, self.influencers, self.memory, self.kpis, self.knowledge)

        return self.memory.tasks()

    def _decide_and_apply(self) -> list[tuple[Decision, Task | None]]:
        # The Decision Engine's only caller: decide_all() computes a fresh
        # verdict per evidenced category every tick — no caching, so this
        # is the entire mechanism behind "nothing is permanently true"
        # (standing architecture, 2026-08-02). A verdict is only persisted
        # (and, if it means "invest"/"propose_capability", acted on) when
        # it's materially different from what's already on record — the
        # same anti-thrash discipline Strategist already applies to
        # reallocation, so recency_score's continuous decay between ticks
        # doesn't spam a new Decision every 30 minutes with nothing behind
        # it.
        # decide_all_with_discovery(), not decision_engine.decide_all()
        # directly -- Executive Discovery's Exploration Before Commitment
        # gate (Mechanism 1) wraps decide() without editing
        # decision_engine.py/decision_apply.py at all (see docs/
        # EXECUTIVE_DISCOVERY_PLACEMENT_DECISION.md); this one-line
        # substitution is the single necessary exception to that
        # document's "zero changes to ceo.py" framing -- named there
        # explicitly, not silently glossed over.
        #
        # docs/DESIGN_BRIDGE_INTEGRATION.md: the one real, disclosed change
        # this integration required in existing code. Previously this loop
        # discarded every (Decision, Task) pair it built and returned None;
        # Bridge 3 needs those real pairs, so they're now collected and
        # returned instead. This touches ceo.py's own orchestration shape
        # only -- decide_all_with_discovery()/apply_decision() themselves,
        # and everything they compute, are completely unchanged.
        decisions_and_tasks: list[tuple[Decision, Task | None]] = []
        for decision in decide_all_with_discovery(self.knowledge, self.memory, self.kpis):
            # A pending capability proposal is only valid while the fresh
            # Decision Engine verdict still supports that proposal. If the
            # evidence falls below threshold, a real channel appears, or any
            # other verdict supersedes it, close the old Goal/Task/Proposal
            # automatically. This reconciliation runs even when the verdict
            # itself is unchanged from the latest persisted Decision, so old
            # runtime state converges without a one-off/manual cleanup hook.
            if decision.verdict not in ("propose_capability", "already_proposed"):
                supersede_pending_capability_proposals(
                    decision.category,
                    self.memory,
                    reason=(
                        f"current Decision Engine verdict {decision.verdict!r} "
                        "no longer supports this capability proposal"
                    ),
                )

            previous = self.decisions.latest_for_category(decision.category)
            if previous is not None:
                if not has_materially_changed(previous, decision):
                    continue
                decision.superseded_id = previous.id

            goal, task = apply_decision(decision)
            if goal is not None:
                self.memory.save_goal(goal)
            if task is not None:
                self.memory.save_task(task)

            self.decisions.save_decision(decision)
            decisions_and_tasks.append((decision, task))

        return decisions_and_tasks

    def _risk_gate_and_delegate(self, task: Task) -> None:
        decision = self.risk_policy.evaluate(task)
        if not decision.requires_approval:
            task.transition("prioritized", f"score={task.priority_score}")
            result = self.delegator.delegate(task, self.registry)
            record_revenue(task, result, self.kpis, self.ledger)
            return

        if is_structural(task.category):
            # Always produce a real Proposal for structural changes, not just
            # a bare "needs approval" flag with no rationale on record.
            self.delegator.delegate(task, self.registry, evidence=decision.reasons)
        else:
            task.transition("pending_approval", "; ".join(decision.reasons))

    def review(self, period: str) -> dict:
        self._evaluate_applied_proposals()
        self._reallocate()

        tasks = self.memory.tasks()
        goals = self.memory.goals()
        candidates = propose_improvements(self.kpis, self.memory.log(), tasks, goals)

        for task in candidates:
            self.memory.save_task(task)
            baseline = {name: self.kpis.latest(name) for name in self.kpis.names()}
            self.delegator.delegate(task, self.registry, evidence=[task.description], baseline_metrics=baseline)
            self.memory.save_task(task)

        return self.reporter.summarize(
            period,
            self.memory,
            self.kpis,
            self.knowledge,
            self.campaigns,
            self.influencers,
            self.brands,
            self.execution_plans,
            self.decisions,
            self.ledger,
            self.conversations,
        )

    def _evaluate_applied_proposals(self) -> None:
        for proposal in self.memory.proposals():
            if proposal.status != "applied":
                continue
            improved = any(
                current is not None and baseline is not None and current > baseline
                for name, baseline in proposal.baseline_metrics.items()
                for current in (self.kpis.latest(name),)
            )
            proposal.status = "confirmed" if improved else "needs_review"
            proposal.resolved_at = now()
            self.memory.save_proposal(proposal)

    def _reallocate(self) -> None:
        # Capital allocation across existing goals — never structural (no
        # asset/agent creation, no Registry dispatch), so it's applied
        # directly rather than routed through RiskPolicy/Proposal: reversible,
        # zero-cost, no privileged access, exactly like a human editing
        # Goal.priority/status by hand today. Always logged so it's visible
        # in the next report, never silent.
        decisions = self.strategist.reallocate(
            self.memory.goals(), self.kpis, self.memory.log(), objective=self.memory.current_strategic_objective()
        )
        for decision in decisions:
            goal = self.memory.get_goal(decision["goal_id"])
            goal.priority = decision["new_priority"]
            goal.status = decision["new_status"]
            self.memory.save_goal(goal)
            self.memory.append_log({**decision, "at": now()})

    def approve(self, task_id: str) -> Task:
        task = self.memory.get_task(task_id)
        linked = [p for p in self.memory.proposals() if p.task_id == task_id and p.status == "pending_approval"]
        if linked:
            proposal = linked[0]
            proposal.status = "applied"
            proposal.resolved_at = now()
            self.memory.save_proposal(proposal)
            # try_complete(), not transition("done", ...) directly (2026-08-17,
            # ONE BRAIN Root Implementation) -- the same guard Monitor
            # respects applies here too, uniformly, so a founder-approved
            # Task that declares expected_outcome still cannot bypass
            # independent verification. Every Task without expected_outcome
            # (today's exact case, always) is completely unaffected.
            task.try_complete(f"proposal {proposal.id} approved and applied")
        else:
            task.transition("ready", "approved by owner")
            result = self.delegator.delegate(task, self.registry)
            record_revenue(task, result, self.kpis, self.ledger)
        self.memory.save_task(task)
        return task

    def reject(self, task_id: str) -> Task:
        task = self.memory.get_task(task_id)
        for proposal in self.memory.proposals():
            if proposal.task_id == task_id and proposal.status == "pending_approval":
                proposal.status = "rejected"
                proposal.resolved_at = now()
                self.memory.save_proposal(proposal)
        task.transition("failed", "rejected by owner")
        self.memory.save_task(task)
        return task
