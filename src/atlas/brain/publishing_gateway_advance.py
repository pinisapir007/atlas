from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.brain.planner import OPEN_STATUSES
from atlas.core.registry import Registry, UnsupportedVerb

PUBLISHING_ASSET_ID = "publishing_gateway"
PUBLISHING_CATEGORY = "publishing_gateway"


def advance_publishing_gateway(tasks: list[Task], registry: Registry, memory: BrainMemory, kpis: KPIRegistry) -> list[Task]:
    """Publishing-Gateway-specific continuation — the sixth application of
    the same bridge pattern (Recruitment, Affiliate Department, Affiliate
    Intelligence, Content Factory, Editorial Review). Three responsibilities:

    1. Trigger package-building once an opportunity is approved_for_marketing.
    2. Request founder approval to queue a READY package — RiskPolicy gates
       this exactly like every other irreversible action in ATLAS.
    3. Handle a rejected queue-approval as a cancellation.

    Also records a queue-status snapshot per goal every cycle, which is how
    the Strategist/executive report sees queue status — no new reporting
    engine, the existing kpi_deltas section already surfaces this.
    """
    try:
        report = registry.dispatch(PUBLISHING_ASSET_ID, "report")
    except (UnsupportedVerb, KeyError):
        return []
    if not isinstance(report, dict):
        return []

    packages = report.get("packages")
    if not isinstance(packages, list):
        return []

    known_goal_ids = {g.id for g in memory.goals()}
    pending_opportunities = report.get("pending_opportunities", [])
    new_tasks: list[Task] = []

    new_tasks.extend(_trigger_build(pending_opportunities, tasks, known_goal_ids))
    new_tasks.extend(_request_queue_approval(packages, tasks, known_goal_ids))
    new_tasks.extend(_handle_cancellations(packages, tasks, known_goal_ids))
    _record_queue_snapshot(packages, known_goal_ids, kpis)

    return new_tasks


def _trigger_build(pending_opportunities: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    if not isinstance(pending_opportunities, list):
        return []

    needs_build_goal_ids = {
        o.get("goal_id")
        for o in pending_opportunities
        if isinstance(o, dict) and o.get("goal_id") in known_goal_ids
    }
    open_nudge_goal_ids = {
        t.goal_id
        for t in tasks
        if t.category == PUBLISHING_CATEGORY and t.source_opportunity_id is None and t.status in OPEN_STATUSES
    }
    return [
        Task(
            goal_id=goal_id,
            description="Build a Publish Package for the approved content",
            category=PUBLISHING_CATEGORY,
            reversible=True,
        )
        for goal_id in needs_build_goal_ids - open_nudge_goal_ids
    ]


def _request_queue_approval(packages: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    new_tasks: list[Task] = []
    for package in packages:
        if not isinstance(package, dict) or package.get("status") != "READY":
            continue
        goal_id = package.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        package_id = package.get("id")
        if not package_id:
            continue

        approval_count = _count(tasks, package_id, reversible=False)
        cancel_trigger_count = _count(tasks, package_id, reversible=True)
        if approval_count != cancel_trigger_count:
            continue  # an approval request for this package is already open or resolved

        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=(
                    f"Approve Queue: publish package ready for '{package.get('title', package_id)}' "
                    f"on {package.get('platform', 'an unspecified platform')}. "
                    "Approve to queue it, or reject to cancel."
                ),
                category=PUBLISHING_CATEGORY,
                reversible=False,  # queuing for eventual real publishing — RiskPolicy gates this
                source_opportunity_id=package_id,  # reused field: holds the PublishPackage id here
            )
        )
    return new_tasks


def _handle_cancellations(packages: list, tasks: list[Task], known_goal_ids: set) -> list[Task]:
    new_tasks: list[Task] = []
    for package in packages:
        if not isinstance(package, dict) or package.get("status") != "READY":
            continue
        goal_id = package.get("goal_id")
        if not goal_id or goal_id not in known_goal_ids:
            continue
        package_id = package.get("id")
        if not package_id:
            continue

        failed_approval_count = _count(tasks, package_id, reversible=False, status="failed")
        cancel_trigger_count = _count(tasks, package_id, reversible=True)
        if failed_approval_count <= cancel_trigger_count:
            continue

        new_tasks.append(
            Task(
                goal_id=goal_id,
                description=f"Cancel publish package '{package.get('title', package_id)}' per founder rejection",
                category=PUBLISHING_CATEGORY,
                reversible=True,
                source_opportunity_id=package_id,
            )
        )
    return new_tasks


_ALL_QUEUE_STATUSES = ("READY", "APPROVED", "QUEUED", "FAILED", "CANCELLED")


def _record_queue_snapshot(packages: list, known_goal_ids: set, kpis: KPIRegistry) -> None:
    # Every status must be recorded every cycle, including zero counts —
    # only recording nonzero statuses left a stale reading behind once a
    # package moved on (e.g. "ready" stuck at 1 forever after the package
    # became "queued", since nothing ever recorded the 0).
    goal_ids_with_packages = {
        p.get("goal_id") for p in packages if isinstance(p, dict) and p.get("goal_id") in known_goal_ids
    }
    counts_by_goal = {goal_id: {status: 0 for status in _ALL_QUEUE_STATUSES} for goal_id in goal_ids_with_packages}

    for package in packages:
        if not isinstance(package, dict):
            continue
        goal_id = package.get("goal_id")
        if goal_id not in counts_by_goal:
            continue
        status = package.get("status", "READY")
        counts_by_goal[goal_id][status] = counts_by_goal[goal_id].get(status, 0) + 1

    for goal_id, counts in counts_by_goal.items():
        for status, count in counts.items():
            kpis.record(f"publish_queue_{status.lower()}_{goal_id}", float(count))


def _count(tasks: list[Task], package_id: str, reversible: bool, status: str | None = None) -> int:
    return sum(
        1
        for t in tasks
        if t.source_opportunity_id == package_id
        and t.category == PUBLISHING_CATEGORY
        and t.reversible is reversible
        and (status is None or t.status == status)
    )
