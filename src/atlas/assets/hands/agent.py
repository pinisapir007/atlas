from atlas.hands.browser_hands import BrowserHands, BrowserHandsError
from atlas.hands.desktop_hands import DesktopHands, DesktopHandsError
from atlas.hands.registry import HandsRequestRegistry

# atlas.hands is a peer, dependency-free-of-brain layer (like
# atlas.campaign/atlas.orchestrator), not part of atlas.core/atlas.brain's
# orchestration -- importing it here is the same precedent
# CampaignExecutionAgent already established for atlas.campaign.


class HandsAgent:
    """The real handler for a risk-gated `hands_execute` Task
    (2026-08-09, Hands V1). Never decides WHAT to do -- ATLAS's brain
    already decided that when it called `request_hands_action()`, and
    RiskPolicy already cleared it (either it was reversible/safe and
    auto-delegated, or a founder explicitly approved it). This agent's
    only job is to look up the real HandsRequest via
    `task.source_opportunity_id` (the same correlation-key precedent
    every other pipeline bridge in this codebase already established)
    and execute its real steps for real, honestly recording exactly
    what happened -- never fabricating success.
    """

    def __init__(
        self,
        hands_requests: HandsRequestRegistry | None = None,
        browser_hands: BrowserHands | None = None,
        desktop_hands: DesktopHands | None = None,
    ) -> None:
        self._hands_requests = hands_requests if hands_requests is not None else HandsRequestRegistry()
        self._browser_hands = browser_hands if browser_hands is not None else BrowserHands()
        self._desktop_hands = desktop_hands if desktop_hands is not None else DesktopHands()

    def run(self, task=None, **kwargs) -> dict:
        request_id = getattr(task, "source_opportunity_id", None)
        if not request_id:
            return {"status": "failed", "error": "no real HandsRequest id on this task"}

        try:
            request = self._hands_requests.get_request(request_id)
        except KeyError:
            return {"status": "failed", "error": f"no real HandsRequest found: {request_id!r}"}

        executor = self._browser_hands if request.executor() == "browser" else self._desktop_hands

        try:
            outcome = executor.execute_steps(request.steps)
        except (BrowserHandsError, DesktopHandsError) as exc:
            request.status = "failed"
            request.results = [{"error": str(exc)}]
            self._hands_requests.save_request(request)
            return {"status": "failed", "hands_request_id": request.id, "error": str(exc)}

        results = outcome["results"] if isinstance(outcome, dict) else outcome
        request.status = "done"
        request.results = results
        self._hands_requests.save_request(request)

        response = {"status": "done", "hands_request_id": request.id, "results": results}
        if isinstance(outcome, dict) and outcome.get("downloaded_files"):
            response["downloaded_files"] = outcome["downloaded_files"]
        return response

    def report(self) -> dict:
        requests = self._hands_requests.requests()
        return {
            "status": "done",
            "total_requests": len(requests),
            "done": len([r for r in requests if r.status == "done"]),
            "failed": len([r for r in requests if r.status == "failed"]),
            "pending": len([r for r in requests if r.status == "pending"]),
        }
