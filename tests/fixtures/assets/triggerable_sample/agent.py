class SampleTriggerable:
    def __init__(self) -> None:
        self.received = []

    def run(self, task=None, **kwargs) -> dict:
        self.received.append(task)
        return {"status": "done", "task_id": getattr(task, "id", None)}

    def report(self) -> dict:
        return {"status": "done", "count": len(self.received)}
