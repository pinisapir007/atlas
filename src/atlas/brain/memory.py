import json
from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Goal, Proposal, StrategicObjective, Task
from atlas.brain.store import BrainStore, JSONFileStore

_EMPTY = {
    "goals": {},
    "tasks": {},
    "proposals": {},
    "kpis": {},
    "log": [],
    "strategic_objectives": {},
    "task_metrics": {"completed_total": 0},
}


def _ensure_compat(data: dict) -> None:
    """Backfill additive BrainMemory schema without a manual migration.

    For a brain.json created before task_metrics existed, the initial
    completed_total is derived exactly once from the currently persisted
    done Tasks. Once present, the counter is durable and never recomputed
    from the live Task collection, so archiving historical Tasks cannot
    make the company's lifetime completion count go backwards.
    """
    data.setdefault("strategic_objectives", {})
    metrics = data.setdefault("task_metrics", {})
    if "completed_total" not in metrics:
        metrics["completed_total"] = sum(
            1
            for task in data.get("tasks", {}).values()
            if isinstance(task, dict) and task.get("status") == "done"
        )


class BrainMemory:
    """Persistent company-level strategic state: goals, tasks, proposals,
    KPI history, and an append-only decision/outcome log.

    Separate from atlas.core.store.JSONStore, which holds per-asset run
    state (a different concern) at .atlas/state.json.

    Storage is delegated to a BrainStore (default: JSONFileStore, atomic
    writes) so a future backend can be swapped in via `store=` without
    changing this class's API or anything that calls it. `path` is kept as
    a convenience for the common case (and for every existing caller that
    already passes one) — it's ignored if `store` is given explicitly.
    """

    def __init__(self, path: Path = Path(".atlas/brain.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    @property
    def path(self) -> Path:
        """The real file this BrainMemory persists to, when its store
        exposes one (P0 Stage 2A, 2026-08-19) -- used to colocate the
        real tick lock (ceo.py) next to the real state it protects, so
        every existing caller/test that already isolates BrainMemory
        via its own tmp_path (the established pattern throughout this
        test suite) gets an isolated lock for free, with no separate
        parameter to remember at any of the ~6 real CEOBrain-constructing
        test helpers. Falls back to JSONFileStore's own default path if
        the real store doesn't expose one (e.g. a future non-file
        backend) -- never raises."""
        return getattr(self._store, "path", Path(".atlas/brain.json"))

    def _read(self) -> dict:
        data = self._store.read()
        if data is None:
            return json.loads(json.dumps(_EMPTY))
        # Tolerates real brain.json files saved before additive schema
        # fields existed, without requiring a separate manual migration.
        _ensure_compat(data)
        return data

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def _update(self, mutator) -> dict:
        """Perform one read-modify-write transaction when supported.

        Real JSONFileStore provides an inter-process-safe update().
        Existing test/future stores that only implement read()/write()
        keep working through the compatibility fallback.
        """
        def apply(data: dict):
            _ensure_compat(data)
            result = mutator(data)
            return data if result is None else result

        update = getattr(self._store, "update", None)
        if callable(update):
            return update(_EMPTY, apply)

        data = self._read()
        updated = apply(data)
        self._write(updated)
        return updated

    def save_goal(self, goal: Goal) -> None:
        def mutate(data):
            data["goals"][goal.id] = asdict(goal)
        self._update(mutate)

    def goals(self) -> list[Goal]:
        return [Goal(**g) for g in self._read()["goals"].values()]

    def get_goal(self, goal_id: str) -> Goal:
        raw = self._read()["goals"].get(goal_id)
        if raw is None:
            raise KeyError(f"no such goal: {goal_id}")
        return Goal(**raw)

    def save_task(self, task: Task) -> None:
        def mutate(data):
            previous = data["tasks"].get(task.id)

            # Count a completion exactly once: only the transition from a
            # missing/non-done persisted record into persisted "done".
            # Re-saving the same completed Task is idempotent.
            if task.status == "done" and (
                previous is None or previous.get("status") != "done"
            ):
                data["task_metrics"]["completed_total"] += 1

            data["tasks"][task.id] = asdict(task)

        self._update(mutate)

    def tasks(self) -> list[Task]:
        return [Task(**t) for t in self._read()["tasks"].values()]

    def get_task(self, task_id: str) -> Task:
        raw = self._read()["tasks"].get(task_id)
        if raw is None:
            raise KeyError(f"no such task: {task_id}")
        return Task(**raw)

    def completed_task_total(self) -> int:
        """Lifetime number of Tasks that reached persisted done state.

        Monotonic by construction and independent of Task archival.
        """
        return int(self._read()["task_metrics"]["completed_total"])

    def save_proposal(self, proposal: Proposal) -> None:
        def mutate(data):
            data["proposals"][proposal.id] = asdict(proposal)
        self._update(mutate)

    def save_capability_supersession(self, goal: Goal, task: Task, proposal: Proposal) -> None:
        """Atomically persist one capability-proposal supersession triplet.

        Goal, Task, and Proposal all live in the same BrainMemory document.
        Writing the three together prevents a crash between separate writes
        from leaving a half-superseded state that could either block a future
        proposal forever or create a duplicate proposal on the next tick.
        Task.transition() must be called by the domain layer before this
        method; this method only persists the already-decided states.
        """
        def mutate(data):
            data["goals"][goal.id] = asdict(goal)
            data["tasks"][task.id] = asdict(task)
            data["proposals"][proposal.id] = asdict(proposal)

        self._update(mutate)

    def proposals(self) -> list[Proposal]:
        return [Proposal(**p) for p in self._read()["proposals"].values()]

    def get_proposal(self, proposal_id: str) -> Proposal:
        raw = self._read()["proposals"].get(proposal_id)
        if raw is None:
            raise KeyError(f"no such proposal: {proposal_id}")
        return Proposal(**raw)

    def record_kpi(self, name: str, value: float, at: str) -> None:
        def mutate(data):
            data["kpis"].setdefault(name, []).append({"at": at, "value": value})
        self._update(mutate)

    def kpi_snapshot(self) -> dict[str, list[dict]]:
        """Return all KPI histories from one BrainMemory read."""
        return self._read()["kpis"]

    def kpi_history(self, name: str) -> list[dict]:
        return self._read()["kpis"].get(name, [])

    def kpi_names(self) -> list[str]:
        return sorted(self._read()["kpis"])

    def append_log(self, entry: dict) -> None:
        def mutate(data):
            data["log"].append(entry)
        self._update(mutate)

    def log(self) -> list[dict]:
        return self._read()["log"]

    def save_strategic_objective(self, objective: StrategicObjective) -> None:
        """Records a new current strategic objective. Never mutates or
        replaces a prior one in place -- full history is kept, the
        same "a changed verdict is a new record" discipline
        DecisionLog already applies. Fail-closed: rejects a real
        weight configuration that doesn't actually describe a
        trade-off (weights must sum to ~1.0), rather than silently
        normalizing a founder's mistake into something else."""
        total = objective.cash_flow_weight + objective.strategic_value_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"cash_flow_weight + strategic_value_weight must sum to 1.0, got {total}"
            )
        def mutate(data):
            data["strategic_objectives"][objective.id] = asdict(objective)
        self._update(mutate)

    def strategic_objectives(self) -> list[StrategicObjective]:
        return [StrategicObjective(**o) for o in self._read()["strategic_objectives"].values()]

    def current_strategic_objective(self) -> StrategicObjective | None:
        """The real current objective -- simply the most recently
        created one, never a separately-tracked pointer that could
        drift out of sync. None means no objective has ever been set,
        the honest default (never a fabricated one)."""
        objectives = self.strategic_objectives()
        if not objectives:
            return None
        return max(objectives, key=lambda o: o.created_at)
