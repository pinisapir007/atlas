import json
from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import Goal, Proposal, Task
from atlas.brain.store import BrainStore, JSONFileStore

_EMPTY = {"goals": {}, "tasks": {}, "proposals": {}, "kpis": {}, "log": []}


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

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else json.loads(json.dumps(_EMPTY))

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_goal(self, goal: Goal) -> None:
        data = self._read()
        data["goals"][goal.id] = asdict(goal)
        self._write(data)

    def goals(self) -> list[Goal]:
        return [Goal(**g) for g in self._read()["goals"].values()]

    def get_goal(self, goal_id: str) -> Goal:
        raw = self._read()["goals"].get(goal_id)
        if raw is None:
            raise KeyError(f"no such goal: {goal_id}")
        return Goal(**raw)

    def save_task(self, task: Task) -> None:
        data = self._read()
        data["tasks"][task.id] = asdict(task)
        self._write(data)

    def tasks(self) -> list[Task]:
        return [Task(**t) for t in self._read()["tasks"].values()]

    def get_task(self, task_id: str) -> Task:
        raw = self._read()["tasks"].get(task_id)
        if raw is None:
            raise KeyError(f"no such task: {task_id}")
        return Task(**raw)

    def save_proposal(self, proposal: Proposal) -> None:
        data = self._read()
        data["proposals"][proposal.id] = asdict(proposal)
        self._write(data)

    def proposals(self) -> list[Proposal]:
        return [Proposal(**p) for p in self._read()["proposals"].values()]

    def get_proposal(self, proposal_id: str) -> Proposal:
        raw = self._read()["proposals"].get(proposal_id)
        if raw is None:
            raise KeyError(f"no such proposal: {proposal_id}")
        return Proposal(**raw)

    def record_kpi(self, name: str, value: float, at: str) -> None:
        data = self._read()
        data["kpis"].setdefault(name, []).append({"at": at, "value": value})
        self._write(data)

    def kpi_history(self, name: str) -> list[dict]:
        return self._read()["kpis"].get(name, [])

    def kpi_names(self) -> list[str]:
        return sorted(self._read()["kpis"])

    def append_log(self, entry: dict) -> None:
        data = self._read()
        data["log"].append(entry)
        self._write(data)

    def log(self) -> list[dict]:
        return self._read()["log"]
