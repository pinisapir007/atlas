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

        kpis.record("tasks_completed", float(memory.completed_task_total()))
        kpis.record("tasks_blocked", float(sum(1 for t in tasks if t.status == "blocked")))
        kpis.record(
            "pending_approvals",
            float(sum(1 for t in tasks if t.status == "pending_approval")),
        )

    def _sync_one(self, task: Task, registry: Registry, memory: BrainMemory) -> None:
        exact = None
        task_result = getattr(registry, "task_result", None)

        if callable(task_result):
            exact = task_result(
                task.id,
                asset_id=task.assigned_asset_id,
            )

        exact_status = (
            exact.get("status")
            if isinstance(exact, dict)
            else None
        )

        if exact_status in ("failed", "error"):
            task.transition(
                "failed",
                f"exact task run result: {exact}",
            )

        elif exact_status == "done":
            task.try_complete(
                f"exact task run result: {exact}"
            )

        else:
            try:
                report = registry.dispatch(
                    task.assigned_asset_id,
                    "report",
                )
            except UnsupportedVerb:
                task.try_complete(
                    "asset does not report status; assumed complete on dispatch"
                )
            else:
                status = (
                    report.get("status")
                    if isinstance(report, dict)
                    else None
                )
                if status in ("failed", "error"):
                    task.transition(
                        "failed",
                        f"asset reported: {report}",
                    )
                else:
                    task.try_complete(
                        f"asset reported: {report}"
                    )

        memory.save_task(task)

        # Close SimplePlanner's lifecycle automatically. A successfully
        # completed exact generic fallback is recorded on the Goal itself,
        # so no historical Task has to remain alive as a sentinel.
        if task.status == "done" and task.description.startswith("Advance goal:"):
            goal = memory.get_goal(task.goal_id)
            expected = f"Advance goal: {goal.description}"
            if task.description == expected and goal.planner_completion_fingerprint != expected:
                goal.planner_completion_fingerprint = expected
                memory.save_goal(goal)

        memory.append_log(
            {
                "at": task.updated_at,
                "task_id": task.id,
                "category": task.category,
                "status": task.status,
                "assigned_asset_id": task.assigned_asset_id,
            }
        )
