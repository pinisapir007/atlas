from atlas.brain.memory import BrainMemory
from atlas.campaign.registry import CampaignRegistry
from atlas.hands.dispatch import request_hands_action
from atlas.hands.registry import HandsRequestRegistry


class CampaignExecutionAgent:
    """Real handler for an approved campaign-execution Task.

    Step 3 bridge:
    once the founder-approved campaign has a real destination URL, this
    agent creates one durable, correlated HandsRequest that opens and
    inspects that destination through ATLAS's existing Hands pipeline.

    It deliberately does NOT claim that anything was published. Publishing
    to an external platform requires a separate, platform-specific action
    sequence with its own honest risk declaration.
    """

    def __init__(
        self,
        campaigns: CampaignRegistry | None = None,
        memory: BrainMemory | None = None,
        hands_requests: HandsRequestRegistry | None = None,
    ) -> None:
        self._campaigns = campaigns if campaigns is not None else CampaignRegistry()
        self._memory = memory if memory is not None else BrainMemory()
        self._hands_requests = hands_requests if hands_requests is not None else HandsRequestRegistry()

    def run(self, task=None, **kwargs) -> dict:
        campaign = self._campaign_for_goal(getattr(task, "goal_id", None))
        if campaign is None:
            return {
                "status": "done",
                "next_step": "no matching campaign found for this task's goal",
            }

        hands_request = self._ensure_destination_inspection(campaign)

        response = {
            "status": "done",
            "campaign_id": campaign.id,
            "product_offer": campaign.product_offer,
        }

        if hands_request is not None:
            response.update(
                {
                    "hands_request_id": hands_request.id,
                    "hands_task_id": hands_request.task_id,
                    "next_step": (
                        f"Content approved for '{campaign.product_offer}'. "
                        f"ATLAS created a real Hands request to open and inspect "
                        f"the approved campaign destination. No publishing event "
                        f"has been claimed. Record real revenue with "
                        f"'atlas campaign revenue record {campaign.id} <amount>' "
                        f"once a sale occurs, and settlement with "
                        f"'atlas campaign settlement record {campaign.id} <amount>' "
                        f"once cash is actually received."
                    ),
                }
            )
            return response

        response["next_step"] = (
            f"Content approved for '{campaign.product_offer}'. "
            f"No real destination URL is configured yet, so ATLAS did not "
            f"fabricate a Hands action or publishing event. Configure a real "
            f"destination before external execution. Record real results with "
            f"'atlas campaign revenue record {campaign.id} <amount>' once a sale "
            f"occurs, and 'atlas campaign settlement record {campaign.id} <amount>' "
            f"once cash is actually received."
        )
        return response

    def report(self) -> dict:
        return {
            "status": "done",
            "active_campaigns": [
                c.id for c in self._campaigns.campaigns() if c.status == "active"
            ],
        }

    def _campaign_for_goal(self, goal_id: str | None):
        if not goal_id:
            return None
        matches = [c for c in self._campaigns.campaigns() if c.goal_id == goal_id]
        return matches[0] if matches else None

    def _ensure_destination_inspection(self, campaign):
        destination_url = str(getattr(campaign, "destination_url", "") or "").strip()
        if not destination_url:
            return None

        description = (
            f"Inspect approved campaign destination before execution: {campaign.id}"
        )

        # Idempotent: repeated dispatch must never create duplicate real-world
        # action requests for the same campaign.
        for existing in self._hands_requests.requests_for_goal(campaign.goal_id):
            if (
                existing.description == description
                and existing.status in ("pending", "done")
            ):
                return existing

        return request_hands_action(
            self._memory,
            self._hands_requests,
            goal_id=campaign.goal_id,
            steps=[
                {
                    "kind": "navigate",
                    "params": {"url": destination_url},
                },
                {
                    "kind": "describe_page",
                    "params": {},
                },
            ],
            reversible=True,
            estimated_amount=0.0,
            involves_privileged_access=False,
            involves_legal_agreement=False,
            description=description,
        )
