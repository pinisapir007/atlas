from datetime import datetime, timedelta, timezone

from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory

PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}


class Reporter:
    """Synthesizes memory + KPIs into a structured executive summary:
    results, opportunities, risks, and recommendations. Plain-dict shaped
    so a future delivery channel (email/Slack) can consume it without
    rework — that channel isn't built here.
    """

    def summarize(self, period: str, memory: BrainMemory, kpis: KPIRegistry) -> dict:
        if period not in PERIOD_DAYS:
            raise ValueError(f"unknown period: {period} (expected one of {sorted(PERIOD_DAYS)})")
        since = (datetime.now(timezone.utc) - timedelta(days=PERIOD_DAYS[period])).isoformat()

        tasks = memory.tasks()
        goals = memory.goals()
        proposals = memory.proposals()

        by_status: dict[str, int] = {}
        for task in tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1

        return {
            "period": period,
            "active_goals": [g.description for g in goals if g.status == "active"],
            "tasks_by_status": by_status,
            "pending_approvals": [
                {"id": t.id, "description": t.description, "category": t.category}
                for t in tasks
                if t.status == "pending_approval"
            ],
            "blocked_opportunities": [
                {
                    "id": t.id,
                    "description": t.description,
                    "reason": t.history[-1]["reason"] if t.history else "",
                }
                for t in tasks
                if t.status == "blocked"
            ],
            "open_proposals": [
                {"id": p.id, "kind": p.kind, "rationale": p.rationale, "status": p.status}
                for p in proposals
                if p.status != "rejected"
            ],
            "kpi_deltas": {name: kpis.delta(name, since) for name in kpis.names()},
            "reallocations": [
                {
                    "goal_id": entry["goal_id"],
                    "description": _goal_description(entry["goal_id"], memory),
                    "horizon": entry.get("horizon"),
                    "old_priority": entry.get("old_priority"),
                    "new_priority": entry.get("new_priority"),
                    "old_status": entry.get("old_status"),
                    "new_status": entry.get("new_status"),
                    "reason": entry.get("reason"),
                }
                for entry in memory.log()
                if entry.get("kind") == "reallocation" and entry.get("at", "") >= since
            ],
        }


def _goal_description(goal_id: str, memory: BrainMemory) -> str:
    try:
        return memory.get_goal(goal_id).description
    except KeyError:
        return ""
