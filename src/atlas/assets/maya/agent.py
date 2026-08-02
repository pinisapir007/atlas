class MayaAgent:
    """Placeholder integration for the MAYA agent.

    Replace the method bodies with real process/API calls once MAYA's
    startup and health-check mechanism is defined.
    """

    def __init__(self) -> None:
        self._running = False
        self._last_task_id = None

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def status(self) -> str:
        return "running" if self._running else "stopped"

    def run(self, task=None, **kwargs) -> dict:
        """Triggerable: accept delegated work from the CEO brain.

        Executes synchronously and reports done immediately — replace with
        a real dispatch to MAYA's own task-execution mechanism once one
        exists.
        """
        self._last_task_id = getattr(task, "id", None)
        return {"status": "done", "task_id": self._last_task_id}

    def report(self) -> dict:
        """Reportable: current state, for the brain's Monitor to read."""
        return {"status": self.status(), "last_task_id": self._last_task_id}
