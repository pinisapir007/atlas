class AffiliateChannel:
    """Affiliate/referral revenue channel: promotes existing products or
    services for a commission. Execution is a placeholder pending a real
    affiliate network integration — replace once one is chosen."""

    name = "affiliate"

    def __init__(self) -> None:
        self._last_result: dict | None = None

    def execute(self, task) -> dict:
        self._last_result = {
            "status": "done",
            "channel": self.name,
            "revenue_generated": 0.0,
            "details": f"queued affiliate promotion for: {task.description}",
        }
        return self._last_result

    def status(self) -> dict:
        return self._last_result or {"status": "idle", "channel": self.name}
