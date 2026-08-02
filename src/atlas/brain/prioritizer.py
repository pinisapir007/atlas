from datetime import datetime
from typing import Protocol

from atlas.brain.models import Goal, Task, now


class Prioritizer(Protocol):
    def score(self, tasks: list[Task], goals_by_id: dict[str, Goal]) -> None: ...


class SimplePrioritizer:
    """Deterministic scoring: goal priority dominates, urgency (task age)
    breaks ties, and large financial commitments are penalized so they
    don't crowd out cheap, fast wins (large amounts also route through
    RiskPolicy for approval regardless).
    """

    def score(self, tasks: list[Task], goals_by_id: dict[str, Goal]) -> None:
        current = now()
        for task in tasks:
            goal = goals_by_id.get(task.goal_id)
            goal_weight = (6 - goal.priority) if goal else 0  # priority 1 -> 5, priority 5 -> 1
            urgency = min(self._age_hours(task.created_at, current), 48) / 48  # saturates after 2 days
            amount_penalty = min(task.estimated_amount / 10_000, 1.0)
            task.priority_score = round(goal_weight * 2 + urgency - amount_penalty, 4)

    @staticmethod
    def _age_hours(created_at: str, current: str) -> float:
        created = datetime.fromisoformat(created_at)
        as_of = datetime.fromisoformat(current)
        return (as_of - created).total_seconds() / 3600
