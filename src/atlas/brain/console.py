from datetime import datetime, timezone

from atlas.brain.cashflow import goal_cash_flow
from atlas.brain.ceo import CEOBrain
from atlas.brain.entity_resolution import detect_pinned_identity_conflicts
from atlas.core.registry import UnsupportedVerb

DEFAULT_STALE_KPI_HOURS = 1.0

CAMPAIGN_STAGES = {
    "selected_for_marketing",
    "content_packaged",
    "editorial_passed",
    "approved_for_marketing",
}


def build_console_view(brain: CEOBrain) -> dict:
    """Read-only aggregation across everything ATLAS already tracks — no new
    state, no new store, no new workflow engine. Just a consolidated view
    over the existing Goal/Task/Registry/KPIRegistry primitives, the same
    ones every CLI command already reads individually. Iterates whatever is
    currently registered rather than a hardcoded department list, so a
    future asset shows up here automatically.
    """
    goals = brain.memory.goals()
    tasks = brain.memory.tasks()

    pending_approvals = [
        {"id": t.id, "category": t.category, "description": t.description, "goal_id": t.goal_id}
        for t in tasks
        if t.status == "pending_approval"
    ]
    blocked = [
        {"id": t.id, "category": t.category, "description": t.description}
        for t in tasks
        if t.status == "blocked"
    ]

    departments = {}
    for record in brain.registry.records():
        if not record.entrypoint:
            continue
        try:
            departments[record.id] = brain.registry.dispatch(record.id, "report")
        except UnsupportedVerb:
            continue  # doesn't implement Reportable — nothing to show, not an error
        except Exception as exc:  # a misbehaving department must never break the console
            departments[record.id] = {"status": "error", "detail": str(exc)}

    kpi_snapshot = brain.kpis.snapshot()

    # Full KPI history remains available to diagnostics/CLI exactly as
    # before. Headquarters gets a separate current-business projection:
    # only metrics explicitly scoped to a goal that is active right now.
    # This keeps retired goals, experiments and research-attempt counters
    # in durable history without presenting them as live company KPIs.
    kpis = {
        name: (history[-1]["value"] if history else None)
        for name, history in sorted(kpi_snapshot.items())
    }

    active_goals = [
        goal
        for goal in goals
        if goal.status == "active"
    ]
    active_goal_ids = {
        goal.id
        for goal in active_goals
    }

    live_kpis = {
        name: value
        for name, value in kpis.items()
        if any(
            name.endswith(f"_{goal_id}")
            for goal_id in active_goal_ids
        )
    }

    return {
        "goals": [
            {
                "id": g.id,
                "description": g.description,
                "priority": g.priority,
                "status": g.status,
                "horizon": g.horizon,
            }
            for g in goals
        ],
        "pending_approvals": pending_approvals,
        "blocked": blocked,
        "departments": departments,
        "kpis": kpis,
        "live_kpis": live_kpis,
        "cash_flow": goal_cash_flow(
            active_goals,
            brain.kpis,
            kpi_snapshot,
        ),
    }


def find_stale_kpis(brain: CEOBrain, threshold_hours: float = DEFAULT_STALE_KPI_HOURS) -> list[tuple[str, float]]:
    """A KPI is "stale" if its most recent reading is older than
    threshold_hours. Deterministic, testable (inject an old "at" timestamp
    directly via BrainMemory.record_kpi), no new store — reads the exact
    same KPIRegistry history every other command already reads."""
    stale: list[tuple[str, float]] = []
    now = datetime.now(timezone.utc)
    kpi_snapshot = brain.kpis.snapshot()
    for name, history in sorted(kpi_snapshot.items()):
        if not history:
            continue
        last_at = datetime.fromisoformat(history[-1]["at"])
        age_hours = (now - last_at).total_seconds() / 3600
        if age_hours > threshold_hours:
            stale.append((name, age_hours))
    return stale


def find_warnings(brain: CEOBrain, view: dict | None = None) -> list[str]:
    """Surface current, actionable founder warnings from existing live
    state. A stopped/idle department is a warning only while real work is
    in flight against that asset. KPI age remains available through
    find_stale_kpis() for diagnostics but is not itself a live warning.

    `view` is an optional, already-computed build_console_view(brain) —
    real bug, found live (2026-08-09) against real production-scale data
    (1771 tasks, a 10MB brain.json): every caller that needs both a view
    and its warnings (get_system_health, build_briefing, and Headquarters'
    own _real_state) was silently recomputing build_console_view() from
    scratch again here, several times over per single request, each pass
    costing real seconds at that scale — compounding into a genuinely
    unresponsive server once a real SSE connection re-ran the whole chain
    every 5 seconds. Passing an already-computed `view` through skips the
    recomputation; omitting it (every existing caller) is unchanged."""
    warnings: list[str] = []
    view = view if view is not None else build_console_view(brain)

    # A registered asset being stopped/idle is not itself a founder-facing
    # problem. It becomes actionable only when real work is currently
    # delegated to that asset. This uses the same in-flight semantics as
    # Headquarters' active-asset indicator and Monitor.
    active_asset_ids = {
        task.assigned_asset_id
        for task in brain.memory.tasks()
        if task.status in {"delegated", "in_progress"}
        and task.assigned_asset_id
    }

    maya_report = view["departments"].get("maya")
    if (
        "maya" in active_asset_ids
        and isinstance(maya_report, dict)
        and maya_report.get("status") == "stopped"
    ):
        warnings.append(
            "MAYA is stopped while real work is assigned to it."
        )

    revenue_report = view["departments"].get("revenue")
    if (
        "revenue" in active_asset_ids
        and isinstance(revenue_report, dict)
        and revenue_report.get("status") == "idle"
    ):
        warnings.append(
            "Revenue is idle while real work is assigned to it."
        )

    for proposal in brain.memory.proposals():
        if proposal.kind == "redesign" and proposal.status == "pending_approval":
            warnings.append(f"Pending redesign proposal: {proposal.rationale} ({proposal.id})")

    # KPI age is diagnostic information, not automatically a current
    # founder-facing problem. Historical experiments, retired goals and
    # no-change metrics legitimately become old. Keep find_stale_kpis()
    # available for explicit diagnostics without polluting live warnings.

    # Identity-conflict warning (2026-08-17, ONE BRAIN Root Implementation):
    # two already-real, persisted Opportunities later found to belong to
    # the same real-world entity -- surfaced here, read-only, exactly
    # like every other warning above, rather than through Proposal
    # (rejected during design: Proposal.task_id is required, recreating
    # the same Task->Goal chicken-and-egg problem this whole mechanism
    # exists to avoid). Never merges/deletes/chooses -- entity_resolution.
    # resolve_canonical_subject() already refuses to improve grouping for
    # this exact case; this only makes the real, unresolved conflict
    # visible to the founder.
    for category, subject_a, subject_b in detect_pinned_identity_conflicts(brain.knowledge, brain.opportunities):
        warnings.append(
            f"Possible duplicate business identity in '{category}': '{subject_a}' and '{subject_b}' "
            "appear to be the same real-world entity but are two separate Opportunities — founder review needed."
        )

    return warnings


def recent_activity(brain: CEOBrain, limit: int = 10) -> list[dict]:
    """The existing append-only decision/outcome log, tail end only — no new
    activity-tracking mechanism, this is the same log Monitor/Strategist
    already write to."""
    return brain.memory.log()[-limit:]


def build_briefing(brain: CEOBrain, view: dict | None = None, warnings: list[str] | None = None) -> str:
    """A narrative reading of the exact same state build_console_view/
    find_warnings already compute — presentation only, no new logic.
    `view`/`warnings` are optional, already-computed values (see
    find_warnings' docstring for why this matters at real production
    scale) — omitting either preserves the exact prior behavior."""
    view = view if view is not None else build_console_view(brain)
    warnings = warnings if warnings is not None else find_warnings(brain, view)
    activity = recent_activity(brain, limit=5)

    lines = ["כן פיני, מאז ההפעלה האחרונה ביצעתי...", ""]

    active_goals = [g for g in view["goals"] if g["status"] == "active"]
    lines.append(f"{len(active_goals)} active goal(s):")
    for g in active_goals:
        lines.append(f"  - {g['description']} (priority {g['priority']}, {g['horizon']})")

    if activity:
        lines.append("")
        lines.append("Recent activity:")
        for entry in activity:
            reason = entry.get("reason") or entry.get("status") or ""
            label = entry.get("description") or entry.get("goal_id") or entry.get("task_id", "")
            lines.append(f"  - {label}: {reason}".strip(": "))

    lines.append("")
    lines.append(f"{len(view['pending_approvals'])} item(s) need your approval right now.")

    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


def get_queue(brain: CEOBrain) -> list[dict]:
    """Reused by both the plain REPL's `queue` command and the full-screen
    app's dashboard panel — one place that knows how to fetch it."""
    try:
        report = brain.registry.dispatch("publishing_gateway", "report")
    except (UnsupportedVerb, KeyError):
        return []
    return report.get("packages", []) if isinstance(report, dict) else []


def get_opportunities(brain: CEOBrain) -> list[dict]:
    try:
        report = brain.registry.dispatch("affiliate_intelligence", "report")
    except (UnsupportedVerb, KeyError):
        return []
    return report.get("opportunities", []) if isinstance(report, dict) else []


def get_campaigns(brain: CEOBrain) -> list[dict]:
    return [o for o in get_opportunities(brain) if isinstance(o, dict) and o.get("stage") in CAMPAIGN_STAGES]


def get_system_health(brain: CEOBrain, warnings: list[str] | None = None) -> dict:
    """Combines warnings with task-status counts — still just reading
    existing Task/Goal state, no new health-tracking mechanism. `warnings`
    is an optional, already-computed find_warnings(brain) result (see
    find_warnings' docstring) — omitting it preserves prior behavior."""
    tasks = brain.memory.tasks()
    return {
        "warnings": warnings if warnings is not None else find_warnings(brain),
        "tasks_blocked": sum(1 for t in tasks if t.status == "blocked"),
        "tasks_failed": sum(1 for t in tasks if t.status == "failed"),
        "tasks_pending_approval": sum(1 for t in tasks if t.status == "pending_approval"),
    }


def summarize_department_report(report) -> str:
    """One-line summary of a department's report(), without assuming its
    exact shape — works for any current or future asset."""
    if not isinstance(report, dict):
        return str(report)
    for key in ("by_stage", "by_status"):
        if key in report and isinstance(report[key], dict):
            nonzero = {k: v for k, v in report[key].items() if v}
            return str(nonzero) if nonzero else "empty"
    return str(report.get("status", "unknown"))


def format_console_view(view: dict) -> str:
    """Shared formatter for the static `atlas console` command and the
    REPL's `status` command — one implementation, not two."""
    lines = ["=== ATLAS Console ==="]

    lines.append(f"\nGoals ({len(view['goals'])}):")
    for g in view["goals"]:
        lines.append(f"  [{g['priority']}] {g['description']} ({g['status']}, {g['horizon']}) — {g['id']}")

    lines.append(f"\nPending Approvals ({len(view['pending_approvals'])}):")
    for a in view["pending_approvals"]:
        lines.append(f"  [{a['category']}] {a['description']} ({a['id']})")

    if view["blocked"]:
        lines.append(f"\nBlocked ({len(view['blocked'])}):")
        for b in view["blocked"]:
            lines.append(f"  [{b['category']}] {b['description']} ({b['id']})")

    lines.append("\nDepartments:")
    for asset_id, report in view["departments"].items():
        lines.append(f"  {asset_id}: {summarize_department_report(report)}")

    lines.append("\nKPIs:")
    for name, value in sorted(view["kpis"].items()):
        lines.append(f"  {name} = {value}")

    lines.append("\nCash Flow:")
    if view["cash_flow"]:
        for entry in view["cash_flow"]:
            lines.append(
                f"  {entry['description']}: revenue={entry['revenue']} cost={entry['cost']} "
                f"profit={entry['profit']} roi={entry['roi']} ({entry['goal_id']})"
            )
    else:
        lines.append("  (no goal has revenue or cost measured yet)")

    return "\n".join(lines)
