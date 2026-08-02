class SampleAgent:
    def __init__(self) -> None:
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def status(self) -> str:
        return "running" if self._running else "stopped"
