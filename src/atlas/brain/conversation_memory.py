"""ConversationMemory (2026-08-09, Memory V1) — the real, durable record
of every Founder<->ATLAS interaction through the console/REPL/app. This
closes a real, total gap (confirmed by direct audit, not assumed): the
REPL/app's own transcript was a plain in-process Python list, discarded
the moment the process exited — ATLAS genuinely could not remember what
was said in a prior session. Every other "memory" dimension the founder
asked for already existed as a durable store (goals/tasks/decisions/
research/campaigns/influencers/brands/...); conversations were the one
real exception.

Same JSONFileStore/BrainStore atomic-write pattern as every other
durable store in this codebase (BrainMemory/KnowledgeBase/DecisionLog/
Ledger/...) — a plain, flat ConversationEntry per real turn, appended,
never mutated (append-only, the same discipline DecisionLog already
established for its own history).
"""

from dataclasses import dataclass, field
from pathlib import Path

from atlas.brain.models import new_id, now
from atlas.brain.store import BrainStore, JSONFileStore


@dataclass
class ConversationEntry:
    input_line: str
    response_summary: str
    id: str = field(default_factory=lambda: new_id("conv"))
    created_at: str = field(default_factory=now)


class ConversationMemory:
    """Durable record of every real console turn — pure CRUD, the same
    shape as every other registry in this codebase. No dialogue logic
    lives here; callers (repl.py/app.py) decide what counts as a turn
    worth recording."""

    def __init__(self, path: Path = Path(".atlas/conversations.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"entries": []}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def record_turn(self, input_line: str, response_summary: str) -> ConversationEntry:
        entry = ConversationEntry(input_line=input_line, response_summary=response_summary)
        data = self._read()
        data["entries"].append(
            {
                "id": entry.id,
                "input_line": entry.input_line,
                "response_summary": entry.response_summary,
                "created_at": entry.created_at,
            }
        )
        self._write(data)
        return entry

    def entries(self) -> list[ConversationEntry]:
        return [ConversationEntry(**e) for e in self._read()["entries"]]

    def recent(self, limit: int = 20) -> list[ConversationEntry]:
        return self.entries()[-limit:]
