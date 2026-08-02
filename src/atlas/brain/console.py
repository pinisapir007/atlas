from datetime import datetime, timezone

from atlas.brain.cashflow import goal_cash_flow
from atlas.brain.ceo import CEOBrain
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

    kpis = {name: brain.kpis.latest(name) for name in brain.kpis.names()}

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
        "cash_flow": goal_cash_flow(goals, brain.kpis),
    }


def find_stale_kpis(brain: CEOBrain, threshold_hours: float = DEFAULT_STALE_KPI_HOURS) -> list[tuple[str, float]]:
    """A KPI is "stale" if its most recent reading is older than
    threshold_hours. Deterministic, testable (inject an old "at" timestamp
    directly via BrainMemory.record_kpi), no new store — reads the exact
    same KPIRegistry history every other command already reads."""
    stale: list[tuple[str, float]] = []
    now = datetime.now(timezone.utc)
    for name in brain.kpis.names():
        history = brain.kpis.history(name)
        if not history:
            continue
        last_at = datetime.fromisoformat(history[-1]["at"])
        age_hours = (now - last_at).total_seconds() / 3600
        if age_hours > threshold_hours:
            stale.append((name, age_hours))
    return stale


def find_warnings(brain: CEOBrain) -> list[str]:
    """Requirement: clearly surface MAYA stopped, Revenue idle, pending
    redesign proposals, and stale KPIs — reusing exactly the data every
    other command already reads (department report()s, memory.proposals(),
    KPIRegistry history), no new detection mechanism."""
    warnings: list[str] = []
    view = build_console_view(brain)

    maya_report = view["departments"].get("maya")
    if isinstance(maya_report, dict) and maya_report.get("status") == "stopped":
        warnings.append("MAYA is stopped — no content/capability is currently running.")

    revenue_report = view["departments"].get("revenue")
    if isinstance(revenue_report, dict) and revenue_report.get("status") == "idle":
        warnings.append("Revenue channels are idle — no channel has executed yet.")

    for proposal in brain.memory.proposals():
        if proposal.kind == "redesign" and proposal.status == "pending_approval":
            warnings.append(f"Pending redesign proposal: {proposal.rationale} ({proposal.id})")

    for name, age_hours in find_stale_kpis(brain):
        warnings.append(f"KPI '{name}' hasn't been updated in {age_hours:.1f}h")

    return warnings


def recent_activity(brain: CEOBrain, limit: int = 10) -> list[dict]:
    """The existing append-only decision/outcome log, tail end only — no new
    activity-tracking mechanism, this is the same log Monitor/Strategist
    already write to."""
    return brain.memory.log()[-limit:]


def build_briefing(brain: CEOBrain) -> str:
    """A narrative reading of the exact same state build_console_view/
    find_warnings already compute — presentation only, no new logic."""
    view = build_console_view(brain)
    warnings = find_warnings(brain)
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


def get_system_health(brain: CEOBrain) -> dict:
    """Combines warnings with task-status counts — still just reading
    existing Task/Goal state, no new health-tracking mechanism."""
    tasks = brain.memory.tasks()
    return {
        "warnings": find_warnings(brain),
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
