from dataclasses import dataclass, field

from atlas.brain.models import ALWAYS_REQUIRES_APPROVAL, Task

REDESIGN_PREFIX = "redesign_"


@dataclass
class RiskDecision:
    requires_approval: bool
    reasons: list[str] = field(default_factory=list)


class RiskPolicy:
    """Fail-closed risk gate.

    A task must affirmatively prove itself safe on every axis (reversible,
    within the amount threshold, no privileged-access or legal-agreement
    involvement, and not a structurally-gated category) to skip human
    approval. Unrecognized or unproven risk defaults to requiring approval,
    not the other way around.
    """

    def __init__(self, amount_threshold: float = 0.0):
        self.amount_threshold = amount_threshold

    def evaluate(self, task: Task) -> RiskDecision:
        reasons = []

        if task.category in ALWAYS_REQUIRES_APPROVAL:
            reasons.append(f"category '{task.category}' always requires approval")
        elif task.category.startswith(REDESIGN_PREFIX):
            reasons.append(f"category '{task.category}' is a redesign — always requires approval")

        if not task.reversible:
            reasons.append("not marked reversible")
        if task.estimated_amount > self.amount_threshold:
            reasons.append(
                f"estimated amount {task.estimated_amount} exceeds threshold {self.amount_threshold}"
            )
        if task.involves_privileged_access:
            reasons.append("involves a privileged access change")
        if task.involves_legal_agreement:
            reasons.append("involves a legal agreement")

        return RiskDecision(requires_approval=bool(reasons), reasons=reasons)
