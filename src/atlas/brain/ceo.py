from atlas.brain.affiliate_intelligence_advance import advance_affiliate_intelligence
from atlas.brain.affiliate_pipeline_advance import advance_affiliate_pipeline
from atlas.brain.content_factory_advance import advance_content_factory
from atlas.brain.creative_agent_advance import advance_creative_agent
from atlas.brain.decision_apply import apply_decision
from atlas.brain.decision_engine import decide_all, has_materially_changed
from atlas.brain.decisions import DecisionLog
from atlas.brain.delegator import Delegator, is_structural
from atlas.brain.editorial_review_advance import advance_editorial_review
from atlas.brain.publishing_gateway_advance import advance_publishing_gateway
from atlas.brain.improvement import propose_improvements
from atlas.brain.intake import absorb_opportunities
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.kpi_intake import record_revenue
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task, now
from atlas.brain.monitor import Monitor
from atlas.brain.pipeline_advance import advance_recruitment_pipeline
from atlas.brain.planner import Planner, SimplePlanner
from atlas.brain.prioritizer import Prioritizer, SimplePrioritizer
from atlas.brain.reporter import Reporter
from atlas.brain.risk import RiskPolicy
from atlas.brain.strategist import SimpleStrategist, Strategist
from atlas.core.registry import Registry

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
    ):
        self.memory = memory if memory is not None else BrainMemory()
        self.registry = registry if registry is not None else Registry()
        self.planner = planner if planner is not None else SimplePlanner()
        self.prioritizer = prioritizer if prioritizer is not None else SimplePrioritizer()
        self.risk_policy = risk_policy if risk_policy is not None else RiskPolicy()
        self.reporter = reporter if reporter is not None else Reporter()
        self.strategist = strategist if strategist is not None else SimpleStrategist()
        self.knowledge = knowledge if knowledge is not None else KnowledgeBase()
        self.decisions = decisions if decisions is not None else DecisionLog()
        self.ledger = ledger if ledger is not None else Ledger()
        self.kpis = KPIRegistry(self.memory)
        self.delegator = Delegator(self.memory)
        self.monitor = Monitor()

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
        goals = self.memory.goals()
        tasks = self.memory.tasks()

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

        for opportunity_task in absorb_opportunities(self.memory.tasks(), self.registry, self.memory, self.knowledge):
            self.memory.save_task(opportunity_task)

        self._decide_and_apply()

        for continuation_task in advance_recruitment_pipeline(self.memory.tasks(), self.registry, self.memory):
            self.memory.save_task(continuation_task)

        for affiliate_task in advance_affiliate_pipeline(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(affiliate_task)

        for intelligence_task in advance_affiliate_intelligence(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(intelligence_task)

        for content_task in advance_content_factory(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(content_task)

        for editorial_task in advance_editorial_review(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(editorial_task)

        for creative_task in advance_creative_agent(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(creative_task)

        for publishing_task in advance_publishing_gateway(self.memory.tasks(), self.registry, self.memory, self.kpis):
            self.memory.save_task(publishing_task)

        return self.memory.tasks()

    def _decide_and_apply(self) -> None:
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
        for decision in decide_all(self.knowledge, self.memory, self.kpis):
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

        return self.reporter.summarize(period, self.memory, self.kpis)

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
        decisions = self.strategist.reallocate(self.memory.goals(), self.kpis, self.memory.log())
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
            task.transition("done", f"proposal {proposal.id} approved and applied")
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
