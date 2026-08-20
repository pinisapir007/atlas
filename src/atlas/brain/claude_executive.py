"""ATLAS <-> Claude Executive Connection V1 (2026-08-05).

The first real, durable record of ATLAS sending a real task to a real
executive (Claude) and receiving a real, structured response back —
built on the dependency-free connector in
atlas.integrations.claude_provider, the same brain-wraps-integration
split provider_ranking.py already draws over Digistore24Provider.

Deliberately minimal, per the founder's explicit scope for this
mission: send one real task, verify one real structured response,
parse it, record it, report success or failure. No Protocol, no
provider registry, no second implementation — there is exactly one
real executive connection today, and generalizing before a second
one exists would be the same premature-abstraction mistake this
codebase has avoided everywhere else.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path

from atlas.brain.models import new_id, now
from atlas.brain.store import BrainStore, JSONFileStore
from atlas.integrations.claude_provider import send_task as _send_task_raw


@dataclass
class ClaudeTaskResult:
    """One real, structured record of a real ATLAS -> Claude
    interaction — exactly what "parse the response" and "record the
    interaction" require, never free text."""

    task: str
    result: str
    is_error: bool
    session_id: str
    duration_ms: int
    total_cost_usd: float
    num_turns: int
    raw: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("claude_task"))
    recorded_at: str = field(default_factory=now)


class ClaudeExecutiveLog:
    """Durable, append-only record of every real ATLAS <-> Claude
    interaction — the same append-only discipline Ledger/DecisionLog
    already use in this codebase, reused rather than reinvented.
    Minimal: record and read back, nothing else."""

    def __init__(self, path: Path = Path(".atlas/claude_executive_log.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"interactions": {}}

    def record(self, result: ClaudeTaskResult) -> None:
        data = self._read()
        data["interactions"][result.id] = asdict(result)
        self._store.write(data)

    def interactions(self) -> list[ClaudeTaskResult]:
        return [ClaudeTaskResult(**i) for i in self._read()["interactions"].values()]


def send_task(task: str, log: ClaudeExecutiveLog | None = None, timeout_seconds: float = 120.0) -> ClaudeTaskResult:
    """The one real function this module exists for: calls the real,
    dependency-free CLI connector, wraps the real response into a
    structured ClaudeTaskResult, records it (via `log`, a real
    ClaudeExecutiveLog by default), and returns it. Raises
    ClaudeCLIError (from atlas.integrations.claude_provider) on any
    real failure — never returns or records a fabricated result.
    """
    if log is None:
        log = ClaudeExecutiveLog()

    payload = _send_task_raw(task, timeout_seconds=timeout_seconds)

    result = ClaudeTaskResult(
        task=task,
        result=payload.get("result", ""),
        is_error=bool(payload.get("is_error", False)),
        session_id=payload.get("session_id", ""),
        duration_ms=payload.get("duration_ms", 0),
        total_cost_usd=payload.get("total_cost_usd", 0.0),
        num_turns=payload.get("num_turns", 0),
        raw=payload,
    )
    log.record(result)
    return result
