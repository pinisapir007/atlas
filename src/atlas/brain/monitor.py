from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.kpi import KPIRegistry
from atlas.core.registry import Registry, UnsupportedVerb

IN_FLIGHT_STATUSES = {"delegated", "in_progress"}


class Monitor:
    """Syncs in-flight tasks against their delegated asset's reported state,
    appends outcomes to the decision log, and refreshes the brain's own
    operational KPIs.

    This is the "learn from results" substrate: a structured history of
    what was tried, delegated to whom, and what happened. No ML is applied
    to it here — that's a future, explicitly separate upgrade — but the
    record it would need already exists.
    """

    def sync(self, tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry) -> None:
        for task in tasks:
            if task.status in IN_FLIGHT_STATUSES:
                self._sync_one(task, registry, memory)

        kpis.record("tasks_completed", float(sum(1 for t in tasks if t.status == "done")))
        kpis.record("tasks_blocked", float(sum(1 for t in tasks if t.status == "blocked")))
        kpis.record(
            "pending_approvals",
            float(sum(1 for t in tasks if t.status == "pending_approval")),
        )

    def _sync_one(self, task: Task, registry: Registry, memory: BrainMemory) -> None:
        try:
            report = registry.dispatch(task.assigned_asset_id, "report")
        except UnsupportedVerb:
            task.transition("done", "asset does not report status; assumed complete on dispatch")
        else:
            status = report.get("status") if isinstance(report, dict) else None
            if status in ("failed", "error"):
                task.transition("failed", f"asset reported: {report}")
            else:
                task.transition("done", f"asset reported: {report}")

        memory.save_task(task)
        memory.append_log(
            {
                "at": task.updated_at,
                "task_id": task.id,
                "category": task.category,
                "status": task.status,
                "assigned_asset_id": task.assigned_asset_id,
            }
        )
