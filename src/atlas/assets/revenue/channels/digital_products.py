class DigitalProductChannel:
    """Digital product revenue channel: packages and sells a digital
    offer (report, ebook, course, etc.). Execution is a placeholder
    pending a real payment/delivery integration — replace once one is
    chosen."""

    name = "digital_product"

    def __init__(self) -> None:
        self._last_result: dict | None = None

    def execute(self, task) -> dict:
        self._last_result = {
            "status": "done",
            "channel": self.name,
            "revenue_generated": 0.0,
            "details": f"queued digital product launch for: {task.description}",
        }
        return self._last_result

    def status(self) -> dict:
        return self._last_result or {"status": "idle", "channel": self.name}
