from atlas.brain.memory import BrainMemory
from atlas.brain.models import now


class KPIRegistry:
    """Generic named business/operational metrics, backed by BrainMemory."""

    def __init__(self, memory: BrainMemory):
        self._memory = memory

    def record(self, name: str, value: float) -> None:
        self._memory.record_kpi(name, value, now())

    def snapshot(self) -> dict[str, list[dict]]:
        """Load every KPI history with one BrainMemory read."""
        return self._memory.kpi_snapshot()

    def history(self, name: str) -> list[dict]:
        return self._memory.kpi_history(name)

    def latest(self, name: str) -> float | None:
        history = self.history(name)
        return history[-1]["value"] if history else None

    def delta(self, name: str, since: str) -> float | None:
        """Change in value from the first reading at/after `since` to the latest."""
        window = [h for h in self.history(name) if h["at"] >= since]
        if len(window) < 2:
            return None
        return window[-1]["value"] - window[0]["value"]

    def names(self) -> list[str]:
        return self._memory.kpi_names()
