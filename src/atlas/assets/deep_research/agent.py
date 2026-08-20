"""DeepResearchAgent -- the real, bounded, multi-step escalation for a
category shallow research (ResearchDiscoveryAgent, dispatched via the
request_research Task Delegator routes automatically) already gave up
on (P0 Independence Mission, 2026-08-18).

Verified gap, not assumed: before this, `research_request.py`'s
MAX_RESEARCH_ATTEMPTS is a real cross-tick bound, but every one of
those attempts runs the exact same fixed query
(research_discovery.agent.CANDIDATE_QUERY_TEMPLATE) against the exact
same real search engine -- structurally shallow (one search, one
navigation, whichever real page happens to rank #1) rather than
adaptive depth. Nothing anywhere in this codebase previously varied the
query, tried a second real angle, or judged "is what I've found so far
actually enough" within a single execution -- the class of work an
interactive Claude session was doing by hand across many browser
actions per mission had no autonomous, tick-driven equivalent. This is
the smallest real closure of that gap: reuse, not reinvention.

Deliberately reuses ResearchDiscoveryAgent.execute_step() (extracted
from its own run() for exactly this purpose) for every real step --
same real BrowserUseObserver, same real quality/subject/role gates,
same real Finding shape, same real, already-proven candidate-extraction
logic. This module adds exactly one new real thing: bounded iteration
with two honest stop conditions beyond MAX_STEPS --
  - ENOUGH_EVIDENCE: decision_engine.MIN_INDEPENDENT_SOURCES real,
    sourced Findings already exist for the category (checked via the
    exact same exploration_gate.sourced_finding_count() decide() and
    the Exploration gate already use -- never a second, invented bar).
  - NO_PROGRESS: a real step completed with zero new Findings -- the
    next step (a differently-worded but structurally identical search)
    is unlikely to do better, so stopping honestly beats burning
    further real provider calls/browser actions for no real gain.
Never a fabricated "found the answer" -- a run that exhausts MAX_STEPS
without clearing the evidence bar returns status="done" with an honest
stop_reason="max_steps_reached", the same class of unresolved-but-
honest outcome research_exhausted() already produces one level up.
"""

from atlas.assets.research_discovery.agent import CANDIDATE_QUERY_TEMPLATE, ResearchDiscoveryAgent
from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.discovery.deep_research_request import category_from_deep_research_task
from atlas.brain.discovery.exploration_gate import sourced_finding_count
from atlas.brain.knowledge import KnowledgeBase
from atlas.integrations.base import AIProvider
from atlas.integrations.browser_use_observer import BrowserUseObserver

MAX_STEPS = 3
SOURCE_NAME = "deep_research"

# Real, distinct query angles -- the actual mechanism behind "depth":
# each step asks a genuinely different real question about the same
# category rather than repeating the one proven-but-narrow shallow
# query. Step 1 deliberately reuses the exact query already validated
# across 6 real categories (research_discovery's own docstring); steps
# 2-3 are new, stated, editable assumptions -- the same "not sacred,
# revisit as real evidence accumulates" class as
# discovery.taxonomy.MAX_RESEARCH_ATTEMPTS.
STEP_QUERY_TEMPLATES = [
    CANDIDATE_QUERY_TEMPLATE,
    "top {category} tools comparison 2026",
    "{category} products reviews 2026",
]


class DeepResearchAgent:
    def __init__(
        self,
        knowledge: KnowledgeBase | None = None,
        observer: BrowserUseObserver | None = None,
        ai_provider: AIProvider | None = None,
    ):
        self._knowledge = knowledge if knowledge is not None else KnowledgeBase()
        # Reuses ResearchDiscoveryAgent's own real step mechanism rather
        # than a second, parallel implementation -- both agents must
        # share the exact same knowledge/observer/ai_provider instances
        # so real Findings saved by an early step are visible to this
        # agent's own ENOUGH_EVIDENCE check on a later step.
        self._research = ResearchDiscoveryAgent(knowledge=self._knowledge, observer=observer, ai_provider=ai_provider)

    def run(self, task=None, **kwargs) -> dict:
        try:
            category = category_from_deep_research_task(task)
        except (ValueError, AttributeError) as exc:
            return {"status": "failed", "reason": f"not a real deep-research task: {exc}"}

        steps: list[dict] = []
        for step_index, template in enumerate(STEP_QUERY_TEMPLATES[:MAX_STEPS], start=1):
            if sourced_finding_count(category, self._knowledge) >= MIN_INDEPENDENT_SOURCES:
                return self._stop(category, "enough_evidence", steps)

            query = template.format(category=category.replace("_", " "))
            step_result = self._research.execute_step(category, query, source=SOURCE_NAME)
            steps.append({"step": step_index, "query": query, **step_result})

            if step_result["status"] == "done" and step_result["findings_created"] == 0:
                return self._stop(category, "no_progress", steps)

        final_stop = "enough_evidence" if sourced_finding_count(category, self._knowledge) >= MIN_INDEPENDENT_SOURCES else "max_steps_reached"
        return self._stop(category, final_stop, steps)

    def report(self) -> dict:
        findings = [f for f in self._knowledge.findings() if f.source == SOURCE_NAME]
        return {"status": "done", "total_findings": len(findings)}

    @staticmethod
    def _stop(category: str, stop_reason: str, steps: list[dict]) -> dict:
        return {
            "status": "done",
            "category": category,
            "stop_reason": stop_reason,
            "steps_taken": len(steps),
            "findings_created": sum(s.get("findings_created", 0) for s in steps),
            "steps": steps,
        }
