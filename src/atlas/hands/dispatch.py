"""request_hands_action() (2026-08-09, Hands V1) — the one real bridge
between "ATLAS's brain wants to perform a real Hands action" and
RiskPolicy/Delegator's existing, unmodified fail-closed gating. No new
gating system is built here — this reuses the EXACT mechanism every
other founder-approval gate in this codebase already reuses (a plain
`Task` with honest risk axes): see e.g. campaign_advance.py's
_missing_brand_task, or how the Affiliate/Content Factory/Editorial
Review/Publishing Gateway pipeline gates every founder decision the
same way.

The caller MUST explicitly declare the real risk profile of the
specific sequence being requested (reversible/estimated_amount/
involves_privileged_access/involves_legal_agreement) — mirroring how
every other real Task creator in this codebase already does, never
inferred from the step kinds themselves. Defaults are fail-closed
(reversible=False, the same default Task itself already has): unless a
caller affirmatively says a sequence is safe, RiskPolicy requires
founder approval before it ever runs.
"""

from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.hands.models import HandsRequest, validate_steps
from atlas.hands.registry import HandsRequestRegistry

HANDS_TASK_CATEGORY = "hands_execute"


def request_hands_action(
    memory: BrainMemory,
    hands_requests: HandsRequestRegistry,
    goal_id: str,
    steps: list[dict],
    *,
    reversible: bool = False,
    estimated_amount: float = 0.0,
    involves_privileged_access: bool = False,
    involves_legal_agreement: bool = False,
    description: str = "",
) -> HandsRequest:
    """Validates and durably records a real Hands action sequence, then
    creates the real, risk-gated Task that is the only thing standing
    between this request and real execution. Returns the saved
    HandsRequest (with `task_id` already set) — real execution happens
    later, whenever RiskPolicy/Delegator/HandsAgent process the real
    Task (immediately, if reversible and safe; only after
    `CEOBrain.approve()`, otherwise)."""
    validate_steps(steps)

    request = HandsRequest(
        goal_id=goal_id,
        steps=steps,
        reversible=reversible,
        estimated_amount=estimated_amount,
        involves_privileged_access=involves_privileged_access,
        involves_legal_agreement=involves_legal_agreement,
        description=description,
    )
    hands_requests.save_request(request)

    task = Task(
        goal_id=goal_id,
        description=description or f"Hands: execute {len(steps)} real step(s) ({request.executor()})",
        category=HANDS_TASK_CATEGORY,
        reversible=reversible,
        estimated_amount=estimated_amount,
        involves_privileged_access=involves_privileged_access,
        involves_legal_agreement=involves_legal_agreement,
        source_opportunity_id=request.id,
    )
    memory.save_task(task)

    request.task_id = task.id
    hands_requests.save_request(request)
    return request
