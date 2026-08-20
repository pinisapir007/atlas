from typing import Protocol

from atlas.brain.models import Goal, Task

OPEN_STATUSES = {
    "proposed",
    "prioritized",
    "ready",
    "pending_approval",
    "delegated",
    "in_progress",
    # "blocked" (2026-08-18, P0 fix): a blocked Task means Delegator found
    # no registered asset for its category -- a structural capability gap,
    # not a transient failure. Recreating an identical Task next tick can
    # never succeed differently (the same category will hit the same "no
    # matching asset" block again), unlike "done"/"failed" (deliberately
    # still excluded: a completed goal legitimately gets a fresh task to
    # keep advancing it, and a failed attempt is genuinely worth retrying).
    # Live-verified before this fix: 1,296 blocked Tasks across 8 Goals,
    # the same 5-6 descriptions duplicated ~150x each over ~3 days at the
    # real 30-minute tick cadence -- pure waste, since no existing
    # mechanism re-evaluates a blocked Task when its capability gap is
    # later closed anyway, so counting it as "already has open work" loses
    # no real retry behavior that existed before this fix.
    "blocked",
}

_CATEGORY_KEYWORDS = {
    "revenue": "analyze_revenue",
    "campaign": "launch_campaign",
    "marketing": "launch_campaign",
    "budget": "reallocate_budget",
}


class Planner(Protocol):
    def plan(self, goals: list[Goal], existing_tasks: list[Task]) -> list[Task]: ...


class SimplePlanner:
    """Deterministic default planner: keeps every active goal moving by
    giving it exactly one open task at a time. Category is inferred from
    keywords in the goal description where a match exists, else "general".

    This is permanent infrastructure, not a stand-in for real strategic
    reasoning. A smarter (e.g. LLM-backed) planner implements the same
    Planner protocol; nothing else in the brain needs to change.
    """

    def plan(self, goals: list[Goal], existing_tasks: list[Task]) -> list[Task]:
        goals_with_open_work = {t.goal_id for t in existing_tasks if t.status in OPEN_STATUSES}

        new_tasks = []
        for goal in goals:
            if goal.status != "active" or goal.id in goals_with_open_work:
                continue
            new_tasks.append(
                Task(
                    goal_id=goal.id,
                    description=f"Advance goal: {goal.description}",
                    category=self._infer_category(goal.description),
                    # SimplePlanner only ever creates plain delegate/analyze/report
                    # work with no financial, access, or legal component — reversible
                    # is true by construction here, unlike the model's conservative
                    # default for tasks of unknown provenance.
                    reversible=True,
                )
            )
        return new_tasks

    @staticmethod
    def _infer_category(description: str) -> str:
        lowered = description.lower()
        for keyword, category in _CATEGORY_KEYWORDS.items():
            if keyword in lowered:
                return category
        return "general"
