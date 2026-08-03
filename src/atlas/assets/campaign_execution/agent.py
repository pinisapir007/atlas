from atlas.campaign.registry import CampaignRegistry

# atlas.campaign is a peer, dependency-free layer (like atlas.integrations),
# not part of atlas.core/atlas.brain's orchestration -- importing it here is
# the same precedent affiliate_department.models already established by
# importing atlas.integrations.


class CampaignExecutionAgent:
    """The real handler for the Execution Orchestrator's
    request_founder_review Task once a founder approves it -- the one real
    hand-off the Orchestrator makes to "a specialized agent" today
    (2026-08-03). Publishing itself stays out of scope (no real
    ContentPublisher exists) -- this agent's job is to honestly acknowledge
    the founder's approval and hand back a concrete, real next action, not
    to fabricate a "published" event that never happened.

    Without this asset, an approved campaign-review Task fell through
    Delegator's unmatched-category fallback to an arbitrary Triggerable
    asset -- a real, verified gap: approval led to a semantically
    meaningless dispatch, not to anything representing what actually needs
    to happen next. Registering a real asset for "campaign_execution" is
    what makes Delegator's own `matched` category lookup find this instead
    of falling through to `unmatched`, the same mechanism every other real
    department in this codebase already relies on -- no special-case
    bypass added anywhere in Delegator/RiskPolicy/CEOBrain.
    """

    def __init__(self, campaigns: CampaignRegistry | None = None) -> None:
        self._campaigns = campaigns if campaigns is not None else CampaignRegistry()

    def run(self, task=None, **kwargs) -> dict:
        campaign = self._campaign_for_goal(getattr(task, "goal_id", None))
        if campaign is None:
            return {"status": "done", "next_step": "no matching campaign found for this task's goal"}
        return {
            "status": "done",
            "campaign_id": campaign.id,
            "product_offer": campaign.product_offer,
            "next_step": (
                f"Content approved for '{campaign.product_offer}'. No real publishing integration exists yet -- "
                f"post it to the target platform(s) yourself, then record real results with "
                f"'atlas campaign revenue record {campaign.id} <amount>' once a sale occurs, and "
                f"'atlas campaign settlement record {campaign.id} <amount>' once cash is actually received."
            ),
        }

    def report(self) -> dict:
        # Aggregate, not task-specific -- Reportable.report() takes no
        # arguments (same shape every other asset's report() already has),
        # so this can't target the one campaign a given dispatch was about.
        # Computed fresh from CampaignRegistry every call, not cached
        # in-memory state -- Registry instances (and therefore any
        # in-memory attribute) don't survive across separate CLI/tick
        # invocations, but a real, durable store does.
        return {"status": "done", "active_campaigns": [c.id for c in self._campaigns.campaigns() if c.status == "active"]}

    def _campaign_for_goal(self, goal_id: str | None):
        if not goal_id:
            return None
        matches = [c for c in self._campaigns.campaigns() if c.goal_id == goal_id]
        return matches[0] if matches else None
